import { useEffect, useRef, useState } from 'react';
import { api, cameraSnapshotUrl } from '../api';
import type { CameraSettings, Zone } from '../types';

interface ZoneEditorProps {
  cameras: CameraSettings[];
  onSaved: () => void;
}

type ZoneKind = 'mask' | 'restricted';

const KIND_INFO: Record<ZoneKind, { color: string; help: string }> = {
  mask: {
    color: 'rgba(0, 0, 0, 0.75)',
    help: 'Mask zones are blacked out before analysis, storage or streaming — those pixels never leave the pipeline.',
  },
  restricted: {
    color: 'rgba(255, 90, 90, 0.35)',
    help: 'Restricted zones raise a warning when a person appears to enter them (e.g. stairs, front door, medicine cabinet).',
  },
};

interface Draft {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export function ZoneEditor({ cameras, onSaved }: ZoneEditorProps) {
  const enabled = cameras.filter((c) => c.enabled);
  const [cameraIdx, setCameraIdx] = useState(0);
  const camera = enabled[Math.min(cameraIdx, enabled.length - 1)];

  const [kind, setKind] = useState<ZoneKind>('mask');
  const [maskZones, setMaskZones] = useState<Zone[]>([]);
  const [restrictedZones, setRestrictedZones] = useState<Zone[]>([]);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [status, setStatus] = useState('');
  const [snapshotTick, setSnapshotTick] = useState(0);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (camera) {
      setMaskZones(camera.mask_zones);
      setRestrictedZones(camera.restricted_zones);
      setStatus('');
    }
  }, [camera]);

  if (!camera) return <p className="empty">No cameras enabled.</p>;

  const zones = kind === 'mask' ? maskZones : restrictedZones;
  const setZones = kind === 'mask' ? setMaskZones : setRestrictedZones;

  const pointerPos = (e: React.PointerEvent): { x: number; y: number } => {
    const rect = boxRef.current!.getBoundingClientRect();
    return {
      x: Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width)),
      y: Math.min(1, Math.max(0, (e.clientY - rect.top) / rect.height)),
    };
  };

  const onPointerDown = (e: React.PointerEvent) => {
    const { x, y } = pointerPos(e);
    setDraft({ x0: x, y0: y, x1: x, y1: y });
    (e.target as Element).setPointerCapture(e.pointerId);
  };

  const onPointerMove = (e: React.PointerEvent) => {
    if (draft) {
      const { x, y } = pointerPos(e);
      setDraft({ ...draft, x1: x, y1: y });
    }
  };

  const onPointerUp = () => {
    if (!draft) return;
    const x = Math.min(draft.x0, draft.x1);
    const y = Math.min(draft.y0, draft.y1);
    const w = Math.abs(draft.x1 - draft.x0);
    const h = Math.abs(draft.y1 - draft.y0);
    setDraft(null);
    if (w > 0.02 && h > 0.02) {
      const label =
        kind === 'restricted'
          ? window.prompt('Label for this restricted zone?', 'restricted area') ??
            'restricted area'
          : '';
      setZones([...zones, { label, x, y, w, h }]);
    }
  };

  const save = async () => {
    try {
      await api.putZones(camera.id, {
        mask_zones: maskZones,
        restricted_zones: restrictedZones,
      });
      setStatus('Saved.');
      setSnapshotTick((t) => t + 1); // refresh snapshot to show new masking
      onSaved();
    } catch (err) {
      setStatus(`Save failed: ${String(err)}`);
    }
  };

  const draftRect = draft && {
    left: `${Math.min(draft.x0, draft.x1) * 100}%`,
    top: `${Math.min(draft.y0, draft.y1) * 100}%`,
    width: `${Math.abs(draft.x1 - draft.x0) * 100}%`,
    height: `${Math.abs(draft.y1 - draft.y0) * 100}%`,
  };

  return (
    <div className="zone-editor">
      <div className="zone-toolbar">
        {enabled.length > 1 && (
          <select
            value={cameraIdx}
            onChange={(e) => setCameraIdx(Number(e.target.value))}
          >
            {enabled.map((cam, i) => (
              <option key={cam.id} value={i}>
                {cam.name}
              </option>
            ))}
          </select>
        )}
        <div className="camera-tabs">
          <button
            className={kind === 'mask' ? 'active' : ''}
            onClick={() => setKind('mask')}
          >
            Privacy masks
          </button>
          <button
            className={kind === 'restricted' ? 'active' : ''}
            onClick={() => setKind('restricted')}
          >
            Restricted zones
          </button>
        </div>
        <button className="btn-primary" onClick={() => void save()}>
          Save zones
        </button>
        {status && <span className="hint">{status}</span>}
      </div>
      <p className="hint">{KIND_INFO[kind].help} Drag on the image to add a zone.</p>

      <div
        className="zone-canvas"
        ref={boxRef}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
      >
        <img
          src={cameraSnapshotUrl(camera.id) + `&tick=${snapshotTick}`}
          alt="Camera snapshot"
          draggable={false}
        />
        {zones.map((zone, i) => (
          <div
            key={zone.id ?? i}
            className="zone-rect"
            style={{
              left: `${zone.x * 100}%`,
              top: `${zone.y * 100}%`,
              width: `${zone.w * 100}%`,
              height: `${zone.h * 100}%`,
              background: KIND_INFO[kind].color,
            }}
          >
            <span>{zone.label || (kind === 'mask' ? 'masked' : 'zone')}</span>
            <button
              className="zone-delete"
              onPointerDown={(e) => e.stopPropagation()}
              onClick={() => setZones(zones.filter((_, j) => j !== i))}
            >
              ✕
            </button>
          </div>
        ))}
        {draftRect && <div className="zone-rect draft" style={draftRect} />}
      </div>
    </div>
  );
}
