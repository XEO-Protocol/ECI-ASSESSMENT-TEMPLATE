import { useCallback, useEffect, useState } from 'react';
import { api } from './api';
import { EventTimeline } from './components/EventTimeline';
import { LivePreview } from './components/LivePreview';
import { SettingsPanel } from './components/SettingsPanel';
import { ZoneEditor } from './components/ZoneEditor';
import { useEvents } from './hooks/useEvents';
import type { Settings } from './types';

type Tab = 'live' | 'timeline' | 'zones' | 'settings';

const TABS: { id: Tab; label: string }[] = [
  { id: 'live', label: '📹 Live' },
  { id: 'timeline', label: '🕒 Timeline' },
  { id: 'zones', label: '⬛ Zones' },
  { id: 'settings', label: '⚙️ Settings' },
];

export default function App() {
  const [tab, setTab] = useState<Tab>('live');
  const [settings, setSettings] = useState<Settings | null>(null);
  const [backendUp, setBackendUp] = useState(false);
  const { events, connected, acknowledge } = useEvents(
    settings?.notifications_enabled ?? true,
  );

  const loadSettings = useCallback(async () => {
    try {
      setSettings(await api.getSettings());
      setBackendUp(true);
    } catch {
      setBackendUp(false);
    }
  }, []);

  useEffect(() => {
    void loadSettings();
    const timer = window.setInterval(() => {
      if (!backendUp) void loadSettings();
    }, 3000);
    return () => window.clearInterval(timer);
  }, [backendUp, loadSettings]);

  const togglePause = async () => {
    if (!settings) return;
    const { paused } = await api.setPaused(!settings.paused);
    setSettings({ ...settings, paused });
  };

  const toggleRecording = async () => {
    if (!settings) return;
    const { recording_enabled } = await api.setRecording(
      !settings.recording_enabled,
    );
    setSettings({ ...settings, recording_enabled });
  };

  const unacked = events.filter(
    (e) => !e.acknowledged && e.severity !== 'info',
  ).length;

  if (!backendUp || !settings) {
    return (
      <div className="app-loading">
        <h2>Safety Monitor</h2>
        <p>
          Waiting for the local backend at 127.0.0.1:8765…
          <br />
          <code>cd backend &amp;&amp; python run.py</code>
        </p>
      </div>
    );
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <h1>Safety Monitor</h1>
        <nav>
          {TABS.map(({ id, label }) => (
            <button
              key={id}
              className={tab === id ? 'active' : ''}
              onClick={() => setTab(id)}
            >
              {label}
              {id === 'timeline' && unacked > 0 && (
                <span className="badge">{unacked}</span>
              )}
            </button>
          ))}
        </nav>

        <div className="privacy-controls">
          <h4>Privacy</h4>
          <button
            className={settings.paused ? 'btn-danger' : ''}
            onClick={() => void togglePause()}
          >
            {settings.paused ? '▶ Resume camera' : '⏸ Pause camera'}
          </button>
          <button onClick={() => void toggleRecording()}>
            {settings.recording_enabled ? '⏺ Recording on' : '⭘ Recording off'}
          </button>
          <p className="hint">
            All data stays on this computer. No cloud upload.
          </p>
        </div>

        <footer className={connected ? 'status-ok' : 'status-bad'}>
          {connected ? '● Connected' : '○ Reconnecting…'}
          {settings.paused && ' · paused'}
        </footer>
      </aside>

      <main>
        {tab === 'live' && (
          <LivePreview cameras={settings.cameras} paused={settings.paused} />
        )}
        {tab === 'timeline' && (
          <EventTimeline events={events} onAcknowledge={(id) => void acknowledge(id)} />
        )}
        {tab === 'zones' && (
          <ZoneEditor cameras={settings.cameras} onSaved={() => void loadSettings()} />
        )}
        {tab === 'settings' && (
          <SettingsPanel settings={settings} onChange={setSettings} />
        )}
      </main>
    </div>
  );
}
