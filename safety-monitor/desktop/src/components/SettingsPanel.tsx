import { useEffect, useState } from 'react';
import { api } from '../api';
import { TrashIcon } from '../icons';
import type { Settings, VisionStatus } from '../types';
import { ConfirmDialog } from './ConfirmDialog';

interface SettingsPanelProps {
  settings: Settings;
  onChange: (settings: Settings) => void;
}

export function SettingsPanel({ settings, onChange }: SettingsPanelProps) {
  const [local, setLocal] = useState<Settings>(settings);
  const [status, setStatus] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [vision, setVision] = useState<VisionStatus | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .health()
      .then((h) => !cancelled && setVision(h.vision))
      .catch(() => !cancelled && setVision(null));
    return () => {
      cancelled = true;
    };
    // re-check after every save so provider errors show up immediately
  }, [settings]);

  const set = <K extends keyof Settings>(key: K, value: Settings[K]) =>
    setLocal((prev) => ({ ...prev, [key]: value }));

  const setCamera = (idx: number, patch: Partial<Settings['cameras'][number]>) =>
    setLocal((prev) => ({
      ...prev,
      cameras: prev.cameras.map((c, i) => (i === idx ? { ...c, ...patch } : c)),
    }));

  const save = async () => {
    try {
      const updated = await api.putSettings(local);
      setLocal(updated);
      onChange(updated);
      setStatus('Settings saved.');
    } catch (err) {
      setStatus(`Save failed: ${String(err)}`);
    }
  };

  const deleteHistory = async () => {
    setConfirmDelete(false);
    try {
      const { deleted_events } = await api.deleteHistory();
      setStatus(`Deleted ${deleted_events} events and all local snapshots/clips.`);
    } catch (err) {
      setStatus(`Delete failed: ${String(err)}`);
    }
  };

  return (
    <div className="settings">
      <section className="card">
        <h3>Monitoring</h3>
        <p className="card-desc">
          How often frames are analyzed and how readily motion is flagged.
        </p>

        <div className="field">
          <span className="field-label">
            Analysis interval
            <span className="value-chip">
              {local.capture_interval_seconds.toFixed(1)}s
            </span>
          </span>
          <input
            type="range"
            min={0.5}
            max={10}
            step={0.5}
            value={local.capture_interval_seconds}
            onChange={(e) =>
              set('capture_interval_seconds', Number(e.target.value))
            }
            aria-label="Analysis interval in seconds"
          />
        </div>

        <div className="field">
          <span className="field-label">
            Motion sensitivity
            <span className="value-chip">
              {Math.round(local.motion_sensitivity * 100)}%
            </span>
          </span>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={local.motion_sensitivity}
            onChange={(e) => set('motion_sensitivity', Number(e.target.value))}
            aria-label="Motion sensitivity"
          />
        </div>

        <div className="field-inline">
          <span>Night hours (for unusual-motion alerts)</span>
          <input
            type="number"
            min={0}
            max={23}
            value={local.night_start_hour}
            onChange={(e) => set('night_start_hour', Number(e.target.value))}
            aria-label="Night start hour"
          />
          <span className="hint">to</span>
          <input
            type="number"
            min={0}
            max={23}
            value={local.night_end_hour}
            onChange={(e) => set('night_end_hour', Number(e.target.value))}
            aria-label="Night end hour"
          />
        </div>

        <div className="field-inline">
          <span>Lying-still alert after</span>
          <input
            type="number"
            min={30}
            value={local.lying_still_seconds}
            onChange={(e) => set('lying_still_seconds', Number(e.target.value))}
            aria-label="Lying still threshold in seconds"
          />
          <span className="hint">seconds</span>
        </div>

        <div className="field-inline">
          <input
            id="notif"
            type="checkbox"
            checked={local.notifications_enabled}
            onChange={(e) => set('notifications_enabled', e.target.checked)}
          />
          <label htmlFor="notif">Desktop notifications</label>
        </div>
      </section>

      <section className="card">
        <h3>AI analysis</h3>
        <p className="card-desc">
          Choose what analyzes the camera frames. Both options run entirely
          on this computer.
        </p>

        <div className="field">
          <span className="field-label">
            Vision provider
            {vision &&
              (vision.error ? (
                <span className="chip chip-alert">Failed</span>
              ) : vision.real ? (
                <span className="chip chip-live">
                  <span className="dot" aria-hidden /> Real — active
                </span>
              ) : (
                <span className="chip chip-sim">Simulated</span>
              ))}
          </span>
          <select
            value={local.ai_provider}
            onChange={(e) => set('ai_provider', e.target.value)}
            aria-label="Vision provider"
          >
            <option value="mock">Mock (simulated detections, for demos)</option>
            <option value="local">
              Real — local person & pose models (MediaPipe, on-device)
            </option>
          </select>
          {local.ai_provider === 'local' && (
            <span className="hint">
              Needs the model files once:{' '}
              <code>python scripts/download_models.py</code> in the backend
              folder, then save. Detection stays fully offline.
            </span>
          )}
          {vision?.error && (
            <span className="hint" style={{ color: 'var(--alert)' }}>
              {vision.error} — AI analysis is off until this is fixed; the
              app never substitutes simulated detections.
            </span>
          )}
        </div>

        {local.ai_provider === 'mock' && (
          <div className="field-inline">
            <input
              id="democycle"
              type="checkbox"
              checked={local.mock_demo_cycle}
              onChange={(e) => set('mock_demo_cycle', e.target.checked)}
            />
            <label htmlFor="democycle">
              Demo cycle (periodically simulates falls, lying-still, smoke
              and door events so you can see the full pipeline)
            </label>
          </div>
        )}
      </section>

      <section className="card">
        <h3>Cameras</h3>
        <p className="card-desc">
          Sources marked simulated are always watermarked in the live view.
        </p>
        {local.cameras.map((camera, i) => (
          <div key={camera.id} className="camera-row">
            <input
              className="grow"
              value={camera.name}
              onChange={(e) => setCamera(i, { name: e.target.value })}
              aria-label="Camera name"
            />
            <select
              value={camera.source_type}
              onChange={(e) =>
                setCamera(i, {
                  source_type: e.target.value as 'webcam' | 'synthetic',
                })
              }
              aria-label="Camera source"
            >
              <option value="synthetic">Synthetic (demo)</option>
              <option value="webcam">Webcam (requires OpenCV)</option>
            </select>
            {camera.source_type === 'webcam' && (
              <input
                type="number"
                min={0}
                title="Device index"
                value={camera.device_index}
                onChange={(e) =>
                  setCamera(i, { device_index: Number(e.target.value) })
                }
              />
            )}
            <label className="field-inline" style={{ marginBottom: 0 }}>
              <input
                type="checkbox"
                checked={camera.enabled}
                onChange={(e) => setCamera(i, { enabled: e.target.checked })}
              />
              Enabled
            </label>
          </div>
        ))}
      </section>

      <div className="actions-row">
        <button className="btn-primary" onClick={() => void save()}>
          Save settings
        </button>
        {status && <span className="hint">{status}</span>}
      </div>

      <section className="card danger-card">
        <h3>Privacy &amp; data</h3>
        <p className="card-desc">
          Everything is stored locally (events database, snapshots, clips).
          Nothing is uploaded anywhere.
        </p>
        <button className="btn-danger-outline" onClick={() => setConfirmDelete(true)}>
          <TrashIcon size={14} /> Delete all history…
        </button>
      </section>

      {confirmDelete && (
        <ConfirmDialog
          title="Delete all history?"
          message="This permanently deletes every event, snapshot and clip stored on this computer. This cannot be undone."
          confirmLabel="Delete everything"
          danger
          onConfirm={() => void deleteHistory()}
          onCancel={() => setConfirmDelete(false)}
        />
      )}
    </div>
  );
}
