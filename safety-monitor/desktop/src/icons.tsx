// Small stroke-icon set (lucide-style geometry, drawn for this app).
// Inline SVG keeps the desktop bundle self-contained — no icon font, no CDN.

interface IconProps {
  size?: number;
  className?: string;
  strokeWidth?: number;
}

function base(props: IconProps) {
  return {
    width: props.size ?? 18,
    height: props.size ?? 18,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: props.strokeWidth ?? 1.8,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    className: props.className,
    'aria-hidden': true,
  };
}

/** Brand mark: a shield holding a steady, watching eye. */
export function LogoIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M12 3l7.5 3v5.6c0 4.3-3 8-7.5 9.4-4.5-1.4-7.5-5.1-7.5-9.4V6L12 3z" />
      <circle cx="12" cy="11" r="2.6" />
      <circle cx="12" cy="11" r="0.6" fill="currentColor" stroke="none" />
    </svg>
  );
}

/** Bitmap watching eye — the calm-instrument brand mark. The pupil
 * carries the accent; everything else is ink. */
export function PixelEyeIcon({
  width = 34,
  className,
}: {
  width?: number;
  className?: string;
}) {
  return (
    <svg
      width={width}
      height={Math.round((width * 9) / 13)}
      viewBox="0 0 13 9"
      fill="currentColor"
      shapeRendering="crispEdges"
      className={className}
      aria-hidden
    >
      <rect x="3" y="1" width="7" height="1" />
      <rect x="1" y="2" width="2" height="1" />
      <rect x="10" y="2" width="2" height="1" />
      <rect x="0" y="3" width="1" height="2" />
      <rect x="12" y="3" width="1" height="2" />
      <rect x="5" y="3" width="3" height="1" />
      <rect x="4" y="4" width="2" height="1" />
      <rect x="7" y="4" width="2" height="1" />
      <rect x="6" y="4" width="1" height="1" fill="var(--accent)" />
      <rect x="1" y="5" width="2" height="1" />
      <rect x="10" y="5" width="2" height="1" />
      <rect x="5" y="5" width="3" height="1" />
      <rect x="3" y="6" width="7" height="1" />
    </svg>
  );
}

export function CameraIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <rect x="2.5" y="6.5" width="13" height="11" rx="2.5" />
      <path d="M15.5 10.5l6-3v9l-6-3" />
    </svg>
  );
}

export function TimelineIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7.5V12l3 2" />
    </svg>
  );
}

export function ZonesIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <rect x="3.5" y="3.5" width="17" height="17" rx="2.5" />
      <rect x="7.5" y="7.5" width="6" height="6" rx="1" />
    </svg>
  );
}

export function SettingsIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M4 7h9M17 7h3M4 17h3M11 17h9" />
      <circle cx="15" cy="7" r="2.2" />
      <circle cx="9" cy="17" r="2.2" />
    </svg>
  );
}

export function PauseIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M9 5.5v13M15 5.5v13" />
    </svg>
  );
}

export function PlayIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M8 5.5l11 6.5-11 6.5z" />
    </svg>
  );
}

export function RecordIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <circle cx="12" cy="12" r="8.5" />
      <circle cx="12" cy="12" r="3" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function InfoIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v5" />
      <circle cx="12" cy="7.8" r="0.7" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function WarningIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M12 4L2.8 19.5h18.4L12 4z" />
      <path d="M12 10v4.5" />
      <circle cx="12" cy="17" r="0.7" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function AlertIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M8.2 3h7.6L21 8.2v7.6L15.8 21H8.2L3 15.8V8.2L8.2 3z" />
      <path d="M12 8v5" />
      <circle cx="12" cy="16.2" r="0.7" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function CheckIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M5 12.5l4.5 4.5L19 7.5" />
    </svg>
  );
}

export function TrashIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M4.5 6.5h15M9.5 6.5V4.8a1.3 1.3 0 011.3-1.3h2.4a1.3 1.3 0 011.3 1.3v1.7M6.5 6.5l.8 12.2a1.8 1.8 0 001.8 1.8h5.8a1.8 1.8 0 001.8-1.8l.8-12.2" />
    </svg>
  );
}

export function SunIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 3v2M12 19v2M4.6 4.6l1.4 1.4M18 18l1.4 1.4M3 12h2M19 12h2M4.6 19.4L6 18M18 6l1.4-1.4" />
    </svg>
  );
}

export function MoonIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M20 13.5A8 8 0 0110.5 4a8 8 0 109.5 9.5z" />
    </svg>
  );
}

export function AgentIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <rect x="5" y="8" width="14" height="10" rx="2.5" />
      <path d="M12 8V5M9.5 21h5" />
      <circle cx="9.3" cy="12.8" r="0.8" fill="currentColor" stroke="none" />
      <circle cx="14.7" cy="12.8" r="0.8" fill="currentColor" stroke="none" />
    </svg>
  );
}

/** Severity → icon, used by the timeline and dialogs. */
export function SeverityIcon({
  severity,
  size,
}: {
  severity: 'info' | 'warning' | 'alert';
  size?: number;
}) {
  if (severity === 'alert') return <AlertIcon size={size} />;
  if (severity === 'warning') return <WarningIcon size={size} />;
  return <InfoIcon size={size} />;
}
