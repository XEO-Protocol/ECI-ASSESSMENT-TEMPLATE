import { useMemo, useState } from 'react';
import { api, eventSnapshotUrl } from '../api';
import type { EventType, SafetyEvent } from '../types';
import { EVENT_TYPE_LABELS } from '../types';
import { ConfirmDialog } from './ConfirmDialog';

interface EventTimelineProps {
  events: SafetyEvent[];
  onAcknowledge: (id: string) => void;
}

const SEVERITY_ICON = { info: 'ℹ️', warning: '⚠️', alert: '🚨' } as const;

function dayLabel(ts: number): string {
  const date = new Date(ts * 1000);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  if (date.toDateString() === today.toDateString()) return 'Today';
  if (date.toDateString() === yesterday.toDateString()) return 'Yesterday';
  return date.toLocaleDateString(undefined, {
    weekday: 'long',
    month: 'short',
    day: 'numeric',
  });
}

export function EventTimeline({ events, onAcknowledge }: EventTimelineProps) {
  const [typeFilter, setTypeFilter] = useState<EventType | 'all'>('all');
  const [unackedOnly, setUnackedOnly] = useState(false);
  const [emergencyFor, setEmergencyFor] = useState<SafetyEvent | null>(null);
  const [actionResult, setActionResult] = useState<string | null>(null);

  const filtered = useMemo(
    () =>
      events.filter(
        (e) =>
          (typeFilter === 'all' || e.type === typeFilter) &&
          (!unackedOnly || !e.acknowledged),
      ),
    [events, typeFilter, unackedOnly],
  );

  const groups = useMemo(() => {
    const map = new Map<string, SafetyEvent[]>();
    for (const event of filtered) {
      const key = dayLabel(event.created_at);
      map.set(key, [...(map.get(key) ?? []), event]);
    }
    return [...map.entries()];
  }, [filtered]);

  const confirmEmergency = async () => {
    if (!emergencyFor) return;
    try {
      // confirmed=true only ever set here, after the explicit dialog above.
      await api.emergencyAction(emergencyFor.id, 'notify_contact', true);
      setActionResult(
        'Action recorded. (MVP: this logs the confirmed action; connect an emergency contact channel in a later phase.)',
      );
    } catch (err) {
      setActionResult(`Action failed: ${String(err)}`);
    }
    setEmergencyFor(null);
  };

  return (
    <div className="timeline">
      <div className="timeline-filters">
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value as EventType | 'all')}
        >
          <option value="all">All event types</option>
          {Object.entries(EVENT_TYPE_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <label>
          <input
            type="checkbox"
            checked={unackedOnly}
            onChange={(e) => setUnackedOnly(e.target.checked)}
          />
          Unreviewed only
        </label>
      </div>

      {actionResult && (
        <div className="banner" onClick={() => setActionResult(null)}>
          {actionResult}
        </div>
      )}

      {groups.length === 0 && <p className="empty">No events yet.</p>}

      {groups.map(([day, dayEvents]) => (
        <section key={day}>
          <h3 className="day-header">{day}</h3>
          {dayEvents.map((event) => (
            <article
              key={event.id}
              className={`event severity-${event.severity} ${event.acknowledged ? 'acked' : ''}`}
            >
              {event.snapshot_path && (
                <img
                  className="event-thumb"
                  src={eventSnapshotUrl(event.id)}
                  alt="Event snapshot"
                  loading="lazy"
                />
              )}
              <div className="event-body">
                <header>
                  <span className="event-icon">
                    {SEVERITY_ICON[event.severity]}
                  </span>
                  <strong>{EVENT_TYPE_LABELS[event.type]}</strong>
                  <time>
                    {new Date(event.created_at * 1000).toLocaleTimeString()}
                  </time>
                  <span className="confidence">
                    ~{Math.round(event.confidence * 100)}%
                  </span>
                </header>
                <p>{event.message}</p>
                {event.agent_assessment && (
                  <div className="assessment">
                    <strong>
                      Agent assessment ({event.agent_assessment.agent_name},
                      risk: {event.agent_assessment.risk_level})
                    </strong>
                    <p>{event.agent_assessment.summary}</p>
                    {event.agent_assessment.recommended_action && (
                      <p className="hint">
                        Suggested: {event.agent_assessment.recommended_action}
                      </p>
                    )}
                  </div>
                )}
                <footer>
                  {!event.acknowledged && (
                    <button onClick={() => onAcknowledge(event.id)}>
                      Mark reviewed
                    </button>
                  )}
                  {event.severity === 'alert' && (
                    <button
                      className="btn-danger"
                      onClick={() => setEmergencyFor(event)}
                    >
                      Emergency action…
                    </button>
                  )}
                </footer>
              </div>
            </article>
          ))}
        </section>
      ))}

      {emergencyFor && (
        <ConfirmDialog
          title="Confirm emergency action"
          message={`This will record an emergency notification for: "${emergencyFor.message}" — the event may be a false alarm, so please check the snapshot first. Proceed?`}
          confirmLabel="Yes, take action"
          danger
          onConfirm={() => void confirmEmergency()}
          onCancel={() => setEmergencyFor(null)}
        />
      )}
    </div>
  );
}
