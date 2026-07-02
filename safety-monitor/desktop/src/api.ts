import type { SafetyEvent, Settings, Zone } from './types';

export const BASE_URL = 'http://127.0.0.1:8765';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!resp.ok) {
    const detail = await resp.text().catch(() => '');
    throw new Error(`${resp.status} ${resp.statusText}: ${detail}`);
  }
  return (await resp.json()) as T;
}

export const api = {
  health: () => request<{ status: string; paused: boolean }>('/api/health'),
  getSettings: () => request<Settings>('/api/settings'),
  putSettings: (settings: Settings) =>
    request<Settings>('/api/settings', {
      method: 'PUT',
      body: JSON.stringify(settings),
    }),
  listEvents: (params: { limit?: number; type?: string } = {}) => {
    const search = new URLSearchParams();
    if (params.limit) search.set('limit', String(params.limit));
    if (params.type) search.set('type', params.type);
    return request<SafetyEvent[]>(`/api/events?${search.toString()}`);
  },
  ackEvent: (id: string) =>
    request(`/api/events/${id}/ack`, { method: 'POST' }),
  setPaused: (paused: boolean) =>
    request<{ paused: boolean }>('/api/privacy/pause', {
      method: 'POST',
      body: JSON.stringify({ paused }),
    }),
  setRecording: (enabled: boolean) =>
    request<{ recording_enabled: boolean }>('/api/privacy/recording', {
      method: 'POST',
      body: JSON.stringify({ enabled }),
    }),
  deleteHistory: () =>
    request<{ deleted_events: number }>('/api/history', { method: 'DELETE' }),
  putZones: (cameraId: string, zones: { mask_zones?: Zone[]; restricted_zones?: Zone[] }) =>
    request(`/api/cameras/${cameraId}/zones`, {
      method: 'PUT',
      body: JSON.stringify(zones),
    }),
  emergencyAction: (eventId: string, action: string, confirmed: boolean) =>
    request<{ executed: string }>('/api/actions/emergency', {
      method: 'POST',
      body: JSON.stringify({ event_id: eventId, action, confirmed }),
    }),
};

export const streamUrl = (cameraId: string) =>
  `${BASE_URL}/api/cameras/${cameraId}/stream`;

export const cameraSnapshotUrl = (cameraId: string) =>
  `${BASE_URL}/api/cameras/${cameraId}/snapshot.jpg?t=${Date.now()}`;

export const eventSnapshotUrl = (eventId: string) =>
  `${BASE_URL}/api/events/${eventId}/snapshot.jpg`;

export const wsUrl = () => `${BASE_URL.replace(/^http/, 'ws')}/ws/events`;
