import { useState } from 'react';
import { streamUrl } from '../api';
import type { CameraSettings } from '../types';

interface LivePreviewProps {
  cameras: CameraSettings[];
  paused: boolean;
}

type FeedState = 'live' | 'simulated' | 'paused';

function feedState(camera: CameraSettings, paused: boolean): FeedState {
  if (paused) return 'paused';
  return camera.source_type === 'synthetic' ? 'simulated' : 'live';
}

const STATE_CHIP: Record<FeedState, { className: string; label: string }> = {
  live: { className: 'chip chip-live', label: 'Live' },
  simulated: { className: 'chip chip-sim', label: 'Simulated' },
  paused: { className: 'chip chip-paused', label: 'Paused' },
};

export function LivePreview({ cameras, paused }: LivePreviewProps) {
  const enabled = cameras.filter((c) => c.enabled);
  const [selected, setSelected] = useState(0);
  const camera = enabled[Math.min(selected, enabled.length - 1)];

  if (!camera) {
    return (
      <p className="empty">No cameras enabled. Add one under Settings.</p>
    );
  }

  const state = feedState(camera, paused);
  const chip = STATE_CHIP[state];

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

      <div className="frame">
        {/* MJPEG stream; masked zones are blacked out by the backend before
            the frame ever leaves the processing pipeline. */}
        <img src={streamUrl(camera.id)} alt={`Live preview: ${camera.name}`} />

        <div className="frame-topbar">
          <span className={chip.className}>
            <span className="dot" aria-hidden />
            {chip.label}
          </span>
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
      </div>

      <div className="frame-meta">
        <span>
          {camera.source_type === 'synthetic'
            ? 'Synthetic demo scene — switch to your webcam in Settings.'
            : `Webcam device ${camera.device_index}`}
        </span>
        {camera.mask_zones.length > 0 && (
          <>
            <span className="sep">·</span>
            <span>
              {camera.mask_zones.length} privacy mask
              {camera.mask_zones.length > 1 ? 's' : ''} active
            </span>
          </>
        )}
      </div>
    </div>
  );
}
