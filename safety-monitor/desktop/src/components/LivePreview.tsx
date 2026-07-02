import { useState } from 'react';
import { streamUrl } from '../api';
import type { CameraSettings } from '../types';

interface LivePreviewProps {
  cameras: CameraSettings[];
  paused: boolean;
}

export function LivePreview({ cameras, paused }: LivePreviewProps) {
  const enabled = cameras.filter((c) => c.enabled);
  const [selected, setSelected] = useState(0);
  const camera = enabled[Math.min(selected, enabled.length - 1)];

  if (!camera) {
    return <p className="empty">No cameras enabled. Add one in Settings.</p>;
  }

  return (
    <div className="live-preview">
      {enabled.length > 1 && (
        <div className="camera-tabs">
          {enabled.map((cam, i) => (
            <button
              key={cam.id}
              className={i === selected ? 'active' : ''}
              onClick={() => setSelected(i)}
            >
              {cam.name}
            </button>
          ))}
        </div>
      )}
      <div className="preview-frame">
        {/* MJPEG stream; masked zones are blacked out by the backend before
            the frame ever leaves the processing pipeline. */}
        <img src={streamUrl(camera.id)} alt={`Live preview: ${camera.name}`} />
        {paused && <div className="preview-overlay">Camera paused</div>}
      </div>
      <p className="hint">
        {camera.source_type === 'synthetic'
          ? 'Demo camera (synthetic scene). Switch to your webcam in Settings.'
          : `Webcam device ${camera.device_index}`}
        {camera.mask_zones.length > 0 &&
          ` · ${camera.mask_zones.length} privacy mask zone(s) active`}
      </p>
    </div>
  );
}
