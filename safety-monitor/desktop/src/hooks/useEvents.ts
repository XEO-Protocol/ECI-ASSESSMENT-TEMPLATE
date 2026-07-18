import { useCallback, useEffect, useRef, useState } from 'react';
import { api, wsUrl } from '../api';
import type { AgentAssessment, SafetyEvent } from '../types';
import { EVENT_TYPE_LABELS } from '../types';

interface WsMessage {
  kind: 'event' | 'assessment' | 'history_deleted' | 'emergency_action';
  event?: SafetyEvent;
  assessment?: AgentAssessment;
}

/**
 * Loads the event history and keeps it live over the backend WebSocket.
 * Fires a desktop notification for warning/alert events.
 */
export function useEvents(notificationsEnabled: boolean) {
  const [events, setEvents] = useState<SafetyEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const notificationsRef = useRef(notificationsEnabled);
  notificationsRef.current = notificationsEnabled;

  const refresh = useCallback(async () => {
    try {
      setEvents(await api.listEvents({ limit: 200 }));
    } catch {
      // backend not up yet; the ws reconnect loop will retry
    }
  }, []);

  useEffect(() => {
    void refresh();
    let ws: WebSocket | null = null;
    let closed = false;
    let retry: number | undefined;
    let keepalive: number | undefined;

    const connect = () => {
      ws = new WebSocket(wsUrl());
      ws.onopen = () => {
        setConnected(true);
        void refresh();
        keepalive = window.setInterval(() => ws?.send('ping'), 20000);
      };
      ws.onmessage = (msg) => {
        const data = JSON.parse(msg.data as string) as WsMessage;
        if (data.kind === 'event' && data.event) {
          const event = data.event;
          setEvents((prev) => [event, ...prev].slice(0, 500));
          if (
            notificationsRef.current &&
            (event.severity === 'warning' || event.severity === 'alert')
          ) {
            const title = `Safety Monitor: ${EVENT_TYPE_LABELS[event.type]}`;
            if (window.electronAPI) {
              void window.electronAPI.notify(title, event.message);
            } else if (Notification.permission === 'granted') {
              new Notification(title, { body: event.message });
            }
          }
        } else if (data.kind === 'assessment' && data.assessment) {
          const assessment = data.assessment;
          setEvents((prev) =>
            prev.map((e) =>
              e.id === assessment.event_id
                ? { ...e, agent_assessment: assessment }
                : e,
            ),
          );
        } else if (data.kind === 'history_deleted') {
          setEvents([]);
        }
      };
      ws.onclose = () => {
        setConnected(false);
        window.clearInterval(keepalive);
        if (!closed) retry = window.setTimeout(connect, 2000);
      };
      ws.onerror = () => ws?.close();
    };

    connect();
    return () => {
      closed = true;
      window.clearTimeout(retry);
      window.clearInterval(keepalive);
      ws?.close();
    };
  }, [refresh]);

  const acknowledge = useCallback(async (id: string) => {
    await api.ackEvent(id);
    setEvents((prev) =>
      prev.map((e) => (e.id === id ? { ...e, acknowledged: true } : e)),
    );
  }, []);

  return { events, connected, refresh, acknowledge, setEvents };
}
