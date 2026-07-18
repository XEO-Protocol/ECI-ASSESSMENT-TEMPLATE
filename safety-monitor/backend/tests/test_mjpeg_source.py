"""Tests for the bounded MJPEG network camera source.

The integration tests run a REAL local HTTP server streaming multipart
JPEG and read frames through MjpegSource over an actual socket — no
stubbed transport.
"""

from __future__ import annotations

import io
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
import pytest
from PIL import Image

from safety_monitor.camera_sources import MjpegSource, create_source


def jpeg_bytes(color, size=(64, 48)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "JPEG", quality=90)
    return buf.getvalue()


class StreamHandler(BaseHTTPRequestHandler):
    """Minimal MJPEG server: streams frames from self.server.frames forever."""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.end_headers()
        try:
            while True:
                for frame in self.server.frames:  # type: ignore[attr-defined]
                    self.wfile.write(
                        b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
                    )
                    time.sleep(0.05)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *args):  # keep test output clean
        pass


@pytest.fixture()
def mjpeg_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), StreamHandler)
    server.frames = [jpeg_bytes((200, 30, 30)), jpeg_bytes((30, 200, 30))]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/video"
    server.shutdown()
    server.server_close()


def wait_for_frame(source: MjpegSource, timeout=8.0) -> np.ndarray | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        frame = source.read()
        if frame is not None:
            return frame
        time.sleep(0.05)
    return None


# --- real-socket integration -------------------------------------------------


def test_reads_frames_from_real_stream(mjpeg_server):
    source = MjpegSource(mjpeg_server)
    try:
        frame = wait_for_frame(source)
        assert frame is not None, "no frame received from live MJPEG stream"
        assert frame.shape == (48, 64, 3)
        assert frame.dtype == np.uint8
    finally:
        source.close()


def test_recovers_frames_are_fresh_not_cached(mjpeg_server):
    source = MjpegSource(mjpeg_server)
    try:
        first = wait_for_frame(source)
        assert first is not None
        # stream alternates red/green; within a second we must see the other
        deadline = time.monotonic() + 4.0
        seen_other = False
        while time.monotonic() < deadline and not seen_other:
            frame = source.read()
            if frame is not None and not np.array_equal(frame, first):
                seen_other = True
            time.sleep(0.05)
        assert seen_other, "stream stuck on a single cached frame"
    finally:
        source.close()


def test_stalled_stream_reports_no_signal_not_stale_frame(mjpeg_server):
    source = MjpegSource(mjpeg_server)
    try:
        assert wait_for_frame(source) is not None
        source.STALE_AFTER = 0.2  # tighten for the test
        with source._lock:
            source._latest_ts = time.monotonic() - 1.0  # simulate stall
        assert source.read() is None
    finally:
        source.close()


def test_dead_server_yields_no_frames_and_reconnect_loop_survives():
    # grab a port with nothing listening
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    source = MjpegSource(f"http://127.0.0.1:{port}/video")
    try:
        time.sleep(0.8)
        assert source.read() is None
        assert source._error is not None
    finally:
        source.close()


# --- bounds & validation --------------------------------------------------------


def test_rejects_non_http_urls():
    for url in ("ftp://x/stream", "file:///etc/passwd", "rtsp://cam/1", ""):
        with pytest.raises(RuntimeError):
            MjpegSource(url) if url else create_source("mjpeg", url=url)


class FakeResp:
    """Feeds crafted byte chunks to the parser (transport-only stub)."""

    def __init__(self, chunks):
        self.chunks = chunks

    def iter_bytes(self):
        yield from self.chunks


@pytest.fixture()
def parser_source():
    """A source whose reader thread points at a dead port, so only our
    manual _consume() calls can produce frames."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    source = MjpegSource(f"http://127.0.0.1:{port}/video")
    yield source
    source.close()


def test_oversized_part_is_dropped_without_growing_buffer(parser_source):
    # a JPEG SOI marker followed by an endless body that never closes
    big = b"\xff\xd8" + b"\x00" * (parser_source.MAX_PART_BYTES + 1024)
    good = jpeg_bytes((10, 10, 200))
    parser_source._consume(FakeResp([big, good]))
    # the good frame after the oversized garbage must still decode
    assert parser_source._latest is not None
    assert parser_source._latest.shape == (48, 64, 3)


def test_corrupt_jpeg_part_is_skipped(parser_source):
    corrupt = b"\xff\xd8" + b"not a real jpeg" + b"\xff\xd9"
    parser_source._consume(FakeResp([corrupt, jpeg_bytes((1, 2, 3))]))
    assert parser_source._latest is not None  # good frame survived the corrupt one
