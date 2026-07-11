import { useCallback, useEffect, useState } from 'react';
import { api } from './api';
import { EventTimeline } from './components/EventTimeline';
import { LivePreview } from './components/LivePreview';
import { SettingsPanel } from './components/SettingsPanel';
import { ZoneEditor } from './components/ZoneEditor';
import { useEvents } from './hooks/useEvents';
import {
  CameraIcon,
  LogoIcon,
  MoonIcon,
  PauseIcon,
  PlayIcon,
  RecordIcon,
  SettingsIcon,
  SunIcon,
  TimelineIcon,
  ZonesIcon,
} from './icons';
import { currentTheme, initTheme, setTheme, type Theme } from './theme';
import type { Settings } from './types';

type Tab = 'live' | 'timeline' | 'zones' | 'settings';

const TABS: { id: Tab; label: string; icon: JSX.Element }[] = [
  { id: 'live', label: 'Live', icon: <CameraIcon /> },
  { id: 'timeline', label: 'Timeline', icon: <TimelineIcon /> },
  { id: 'zones', label: 'Zones', icon: <ZonesIcon /> },
  { id: 'settings', label: 'Settings', icon: <SettingsIcon /> },
];

const PAGE_COPY: Record<Tab, { title: string; sub: string }> = {
  live: {
    title: 'Live view',
    sub: 'Watching locally — frames are analyzed and stored on this computer only.',
  },
  timeline: {
    title: 'Timeline',
    sub: 'Possible events flagged for your review. Nothing here is a certainty.',
  },
  zones: {
    title: 'Zones',
    sub: 'Draw privacy masks and restricted areas directly on the camera image.',
  },
  settings: {
    title: 'Settings',
    sub: 'Monitoring behavior, AI analysis, cameras, and your data.',
  },
};

initTheme();

export default function App() {
  const [tab, setTab] = useState<Tab>('live');
  const [settings, setSettings] = useState<Settings | null>(null);
  const [backendUp, setBackendUp] = useState(false);
  const [theme, setThemeState] = useState<Theme>(currentTheme());
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

  const toggleTheme = () => {
    const next: Theme = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    setThemeState(next);
  };

  const unacked = events.filter(
    (e) => !e.acknowledged && e.severity !== 'info',
  ).length;

  if (!backendUp || !settings) {
    return (
      <div className="boot">
        <div className="boot-logo">
          <LogoIcon size={30} />
        </div>
        <div className="spinner" aria-hidden />
        <h2>Backend unavailable — reconnecting…</h2>
        <p>
          Monitoring in this window resumes when the local service responds.
          No cached or simulated data is shown in its place.
        </p>
        <p>
          Start it manually with <code>cd backend &amp;&amp; python run.py</code>
        </p>
      </div>
    );
  }

  const copy = PAGE_COPY[tab];

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <LogoIcon size={20} />
          </div>
          <div>
            <h1>Safety Monitor</h1>
            <span className="brand-sub">local-first · private</span>
          </div>
        </div>

        <nav className="nav">
          {TABS.map(({ id, label, icon }) => (
            <button
              key={id}
              className={`nav-item ${tab === id ? 'active' : ''}`}
              onClick={() => setTab(id)}
            >
              {icon}
              <span>{label}</span>
              {id === 'timeline' && unacked > 0 && (
                <span className="badge">{unacked}</span>
              )}
            </button>
          ))}
        </nav>

        <div className="privacy-card">
          <span className="card-eyebrow microcaps">Privacy</span>
          <button className="switch-row" onClick={() => void togglePause()}>
            {settings.paused ? <PlayIcon size={15} /> : <PauseIcon size={15} />}
            <span className="switch-label">
              {settings.paused ? 'Paused' : 'Watching'}
            </span>
            <span
              className={`switch ${settings.paused ? 'warn-on' : 'on'}`}
              aria-hidden
            >
              <i />
            </span>
          </button>
          <button className="switch-row" onClick={() => void toggleRecording()}>
            <RecordIcon size={15} />
            <span className="switch-label">Recording</span>
            <span
              className={`switch ${settings.recording_enabled ? 'on' : ''}`}
              aria-hidden
            >
              <i />
            </span>
          </button>
          <p className="privacy-note">
            Everything stays on this computer. No cloud, no account, no
            telemetry.
          </p>
        </div>

        <div className="side-foot">
          <span className={`conn ${connected ? 'ok' : 'bad'}`}>
            <span className="conn-dot" aria-hidden />
            {connected ? 'Connected' : 'Reconnecting…'}
            {settings.paused && ' · paused'}
          </span>
          <button
            className="theme-btn"
            onClick={toggleTheme}
            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
          >
            {theme === 'dark' ? <SunIcon size={15} /> : <MoonIcon size={15} />}
          </button>
        </div>
      </aside>

      <main className="main">
        <header className="page-head">
          <div className="page-titles">
            <h2>{copy.title}</h2>
            <p className="page-sub">{copy.sub}</p>
          </div>
        </header>

        {tab === 'live' && (
          <LivePreview cameras={settings.cameras} paused={settings.paused} />
        )}
        {tab === 'timeline' && (
          <EventTimeline
            events={events}
            onAcknowledge={(id) => void acknowledge(id)}
          />
        )}
        {tab === 'zones' && (
          <ZoneEditor
            cameras={settings.cameras}
            onSaved={() => void loadSettings()}
          />
        )}
        {tab === 'settings' && (
          <SettingsPanel settings={settings} onChange={setSettings} />
        )}
      </main>
    </div>
  );
}
