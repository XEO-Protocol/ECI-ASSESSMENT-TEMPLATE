import { useEffect, useState } from 'react';
import { streamUrl } from '../api';
import type { CameraSettings, VisionStatus } from '../types';

interface LivePreviewProps {
  cameras: CameraSettings[];
  paused: boolean;
  vision: VisionStatus | null;
}

type FeedState = 'live' | 'simulated' | 'paused';

function feedState(camera: CameraSettings, paused: boolean): FeedState {
  if (paused) return 'paused';
  return camera.source_type === 'synthetic' ? 'simulated' : 'live';
}

const SOURCE_META: Record<CameraSettings['source_type'], (c: CameraSettings) => string> = {
  synthetic: () => 'Synthetic demo scene — switch to a real camera in Settings.',
  webcam: (c) => `Webcam device ${c.device_index}`,
  mjpeg: (c) => `Network camera: ${c.url || 'no URL set'}`,
  phone: () => 'Paired phone camera — streams only over your Wi-Fi.',
};

/** Ticking wall-clock for the frame's data strip. */
function useTick(): string {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(t);
  }, []);
  return now.toLocaleTimeString(undefined, { hour12: false });
}

export function LivePreview({ cameras, paused, vision }: LivePreviewProps) {
  const enabled = cameras.filter((c) => c.enabled);
  const [selected, setSelected] = useState(0);
  const camera = enabled[Math.min(selected, enabled.length - 1)];
  const clock = useTick();

  if (!camera) {
    return (
      <p className="empty">
        No cameras enabled — add one under Settings, or pair a phone by QR
        code.
      </p>
    );
  }

  const state = feedState(camera, paused);
  const aiLabel = vision
    ? vision.error
      ? 'AI OFF'
      : vision.real
        ? 'AI REAL · ON-DEVICE'
        : 'AI MOCK'
    : 'AI —';

  return (
    <div className="live-wrap">
      {enabled.length > 1 && (
        <div className="cam-tabs">
          {enabled.map((cam, i) => (
            <button
              key={cam.id}
              className={`cam-tab ${i === selected ? 'active' : ''}`}
              onClick={() => setSelected(i)}
            >
              {cam.name}
            </button>
          ))}
        </div>
      )}

      <div className="frame-wrap">
        <div className="frame-inner">
          <div className="frame">
            {/* MJPEG stream; masked zones are blacked out by the backend
                before the frame ever leaves the processing pipeline. */}
            <img
              src={streamUrl(camera.id)}
              alt={`Live preview: ${camera.name}`}
            />

            <div className="frame-topbar">
              {state === 'live' && (
                <span className="fchip fchip-live">
                  <span className="dot" aria-hidden />
                  LIVE
                </span>
              )}
              {state === 'simulated' && (
                <span className="fchip fchip-sim">
                  <span className="dot" aria-hidden />
                  SIMULATED
                </span>
              )}
              {state === 'paused' && (
                <span className="fchip fchip-paused">PAUSED</span>
              )}
              <span className="frame-name">{camera.name}</span>
            </div>

            {/* A simulated feed must always say so, persistently. */}
            {camera.source_type === 'synthetic' && !paused && (
              <span className="sim-watermark microcaps">Simulated feed</span>
            )}

            {paused && (
              <div className="frame-overlay">
                <span className="microcaps">Camera paused</span>
                <p>No frames are being read while paused.</p>
              </div>
            )}

            <div className="frame-strip">
              <span>
                {clock} · 8 FPS
              </span>
              <span>
                {camera.mask_zones.length > 0
                  ? `MASKS ${camera.mask_zones.length} · `
                  : ''}
                {aiLabel}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="frame-meta">
        <span>{SOURCE_META[camera.source_type](camera)}</span>
      </div>
    </div>
  );
}
