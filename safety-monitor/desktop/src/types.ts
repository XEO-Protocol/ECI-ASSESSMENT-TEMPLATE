// Mirrors the backend pydantic models (safety_monitor/models.py).

export type EventType =
  | 'motion'
  | 'person_detected'
  | 'possible_fall'
  | 'person_lying_still'
  | 'stove_unattended'
  | 'smoke_flame_anomaly'
  | 'door_left_open'
  | 'restricted_zone_entry'
  | 'unusual_night_motion';

export type Severity = 'info' | 'warning' | 'alert';

export interface Zone {
  id?: string;
  label: string;
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface AgentAssessment {
  event_id: string;
  agent_name: string;
  summary: string;
  risk_level: 'none' | 'low' | 'medium' | 'high';
  recommended_action: string;
  requires_user_confirmation: boolean;
  created_at: number;
}

export interface SafetyEvent {
  id: string;
  camera_id: string;
  type: EventType;
  severity: Severity;
  confidence: number;
  message: string;
  created_at: number;
  snapshot_path: string | null;
  clip_dir: string | null;
  acknowledged: boolean;
  agent_assessment: AgentAssessment | null;
}

export interface CameraSettings {
  id: string;
  name: string;
  source_type: 'webcam' | 'synthetic';
  device_index: number;
  enabled: boolean;
  mask_zones: Zone[];
  restricted_zones: Zone[];
}

export interface Settings {
  capture_interval_seconds: number;
  motion_sensitivity: number;
  night_start_hour: number;
  night_end_hour: number;
  lying_still_seconds: number;
  stove_unattended_seconds: number;
  door_open_seconds: number;
  notifications_enabled: boolean;
  recording_enabled: boolean;
  paused: boolean;
  ai_provider: string;
  mock_demo_cycle: boolean;
  cameras: CameraSettings[];
}

export const EVENT_TYPE_LABELS: Record<EventType, string> = {
  motion: 'Motion',
  person_detected: 'Person detected',
  possible_fall: 'Possible fall',
  person_lying_still: 'Person lying still',
  stove_unattended: 'Stove possibly unattended',
  smoke_flame_anomaly: 'Smoke/flame-like anomaly',
  door_left_open: 'Door left open',
  restricted_zone_entry: 'Restricted zone entry',
  unusual_night_motion: 'Unusual motion at night',
};

declare global {
  interface Window {
    electronAPI?: {
      notify: (title: string, body: string) => Promise<void>;
      backendUrl: () => Promise<string>;
    };
  }
}
