import { useCallback, useEffect, useState } from 'react';
import { api } from './api';
import { EventTimeline } from './components/EventTimeline';
import { LivePreview } from './components/LivePreview';
import { SettingsPanel } from './components/SettingsPanel';
import { ZoneEditor } from './components/ZoneEditor';
import { useEvents } from './hooks/useEvents';
import { MoonIcon, PixelEyeIcon, SunIcon } from './icons';
import { currentTheme, initTheme, setTheme, type Theme } from './theme';
import type { Settings, VisionStatus } from './types';

type Tab = 'live' | 'timeline' | 'zones' | 'settings';

const TABS: { id: Tab; label: string }[] = [
  { id: 'live', label: 'Live' },
  { id: 'timeline', label: 'Timeline' },
  { id: 'zones', label: 'Zones' },
  { id: 'settings', label: 'Settings' },
];

initTheme();

function Clock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(t);
  }, []);
  return (
    <div className="clock">
      <b>
        {now.toLocaleTimeString(undefined, {
          hour: '2-digit',
          minute: '2-digit',
        })}
      </b>
      {now.toLocaleDateString(undefined, {
        weekday: 'short',
        day: '2-digit',
        month: 'short',
      })}
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState<Tab>('live');
  const [settings, setSettings] = useState<Settings | null>(null);
  const [vision, setVision] = useState<VisionStatus | null>(null);
  const [backendUp, setBackendUp] = useState(false);
  const [theme, setThemeState] = useState<Theme>(currentTheme());
  const { events, connected, acknowledge } = useEvents(
    settings?.notifications_enabled ?? true,
  );

  const loadSettings = useCallback(async () => {
    try {
      setSettings(await api.getSettings());
      setBackendUp(true);
      api
        .health()
        .then((h) => setVision(h.vision))
        .catch(() => setVision(null));
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
          <PixelEyeIcon width={38} />
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

  // The Live headline is a real reading: it derives from unreviewed
  // warnings/alerts, and its language stays hedged.
  const headline =
    tab === 'live' ? (
      unacked > 0 ? (
        <>
          <span className="loud-alert">Something may need you.</span>
        </>
      ) : (
        <>
          <span className="quiet">All quiet,</span> nothing needs you.
        </>
      )
    ) : null;

  const PAGE: Record<Tab, { eyebrow: string; sub: string }> = {
    live: {
      eyebrow: settings.paused ? 'LIVE // PAUSED' : 'LIVE // WATCHING',
      sub:
        unacked > 0
          ? `${unacked} unreviewed event${unacked > 1 ? 's' : ''} in the timeline · nothing here is a certainty`
          : 'Frames are analyzed and stored on this computer only',
    },
    timeline: {
      eyebrow: 'TIMELINE // LOGBOOK',
      sub: 'Possible events flagged for review · nothing here is a certainty',
    },
    zones: {
      eyebrow: 'ZONES // PRIVACY MASKS & RESTRICTED AREAS',
      sub: 'Masked pixels never leave the pipeline',
    },
    settings: {
      eyebrow: 'SETTINGS // MONITORING · AI · CAMERAS · DATA',
      sub: 'Everything stays on this machine',
    },
  };

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">
            <PixelEyeIcon width={34} />
          </span>
          <div>
            <h1>SENTINEL</h1>
            <span className="brand-sub">Local watch deck</span>
          </div>
        </div>

        <nav className="nav">
          {TABS.map(({ id, label }) => (
            <button
              key={id}
              className={`nav-item ${tab === id ? 'active' : ''}`}
              aria-current={tab === id ? 'page' : undefined}
              onClick={() => setTab(id)}
            >
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
            <span className="switch-label">
              {settings.paused ? 'Paused' : 'Watching'}
            </span>
            <span
              className={`pill ${settings.paused ? 'warn-on' : 'on'}`}
              aria-hidden
            >
              {settings.paused ? 'OFF' : 'ON'} <i />
            </span>
          </button>
          <button className="switch-row" onClick={() => void toggleRecording()}>
            <span className="switch-label">Recording</span>
            <span
              className={`pill ${settings.recording_enabled ? 'on' : ''}`}
              aria-hidden
            >
              {settings.recording_enabled ? 'ON' : 'OFF'} <i />
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
            {connected ? 'Link OK' : 'Relinking…'}
          </span>
          <button
            className="theme-btn"
            onClick={toggleTheme}
            title={`Switch to ${theme === 'dark' ? 'day' : 'night'} face`}
          >
            {theme === 'dark' ? <SunIcon size={15} /> : <MoonIcon size={15} />}
          </button>
        </div>
      </aside>

      <main className="main">
        <header className="page-head">
          <div className="page-titles">
            <span className="page-eyebrow microcaps">{PAGE[tab].eyebrow}</span>
            <h2>
              {headline ??
                TABS.find((t) => t.id === tab)!.label}
            </h2>
            <p className="page-sub">{PAGE[tab].sub}</p>
          </div>
          <Clock />
        </header>

        {tab === 'live' && (
          <LivePreview
            cameras={settings.cameras}
            paused={settings.paused}
            vision={vision}
          />
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
