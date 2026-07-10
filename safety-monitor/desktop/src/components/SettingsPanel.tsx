import { useState } from 'react';
import { api } from '../api';
import type { Settings } from '../types';
import { ConfirmDialog } from './ConfirmDialog';

interface SettingsPanelProps {
  settings: Settings;
  onChange: (settings: Settings) => void;
}

export function SettingsPanel({ settings, onChange }: SettingsPanelProps) {
  const [local, setLocal] = useState<Settings>(settings);
  const [status, setStatus] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(false);

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
      <section>
        <h3>Monitoring</h3>
        <label>
          Analysis interval: {local.capture_interval_seconds.toFixed(1)}s
          <input
            type="range"
            min={0.5}
            max={10}
            step={0.5}
            value={local.capture_interval_seconds}
            onChange={(e) =>
              set('capture_interval_seconds', Number(e.target.value))
            }
          />
        </label>
        <label>
          Motion sensitivity: {Math.round(local.motion_sensitivity * 100)}%
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={local.motion_sensitivity}
            onChange={(e) => set('motion_sensitivity', Number(e.target.value))}
          />
        </label>
        <label>
          Night hours (for unusual-motion alerts):
          <span className="inline-inputs">
            <input
              type="number"
              min={0}
              max={23}
              value={local.night_start_hour}
              onChange={(e) => set('night_start_hour', Number(e.target.value))}
            />
            to
            <input
              type="number"
              min={0}
              max={23}
              value={local.night_end_hour}
              onChange={(e) => set('night_end_hour', Number(e.target.value))}
            />
          </span>
        </label>
        <label>
          Lying-still alert after (seconds):
          <input
            type="number"
            min={30}
            value={local.lying_still_seconds}
            onChange={(e) => set('lying_still_seconds', Number(e.target.value))}
          />
        </label>
        <label>
          <input
            type="checkbox"
            checked={local.notifications_enabled}
            onChange={(e) => set('notifications_enabled', e.target.checked)}
          />
          Desktop notifications
        </label>
      </section>

      <section>
        <h3>AI analysis</h3>
        <p className="hint">
          Provider: <code>{local.ai_provider}</code> — the MVP ships with mock
          analysis (simulated detections). Real local vision models plug in via
          the VisionProvider interface in the backend.
        </p>
        <label>
          <input
            type="checkbox"
            checked={local.mock_demo_cycle}
            onChange={(e) => set('mock_demo_cycle', e.target.checked)}
          />
          Demo cycle (mock provider periodically simulates falls, lying-still,
          smoke and door events so you can see the full pipeline)
        </label>
      </section>

      <section>
        <h3>Cameras</h3>
        {local.cameras.map((camera, i) => (
          <div key={camera.id} className="camera-row">
            <input
              value={camera.name}
              onChange={(e) => setCamera(i, { name: e.target.value })}
            />
            <select
              value={camera.source_type}
              onChange={(e) =>
                setCamera(i, {
                  source_type: e.target.value as 'webcam' | 'synthetic',
                })
              }
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
            <label>
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

      <div className="settings-actions">
        <button className="btn-primary" onClick={() => void save()}>
          Save settings
        </button>
        {status && <span className="hint">{status}</span>}
      </div>

      <section className="danger-zone">
        <h3>Privacy &amp; data</h3>
        <p className="hint">
          Everything is stored locally (events database, snapshots, clips).
          Nothing is uploaded anywhere.
        </p>
        <button className="btn-danger" onClick={() => setConfirmDelete(true)}>
          Delete all history…
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
