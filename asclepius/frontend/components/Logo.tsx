import { useId } from "react";

interface LogoProps {
  size?: number;
  className?: string;
}

/**
 * The Asclepius mark: the Rod of Asclepius as a clean glyph on an accent tile.
 * This is the ONLY brand mark in the app (sidebar, landing, headers, favicon),
 * and it takes its colours from the active theme.
 */
export function Logo({ size = 24, className }: LogoProps) {
  const gradId = `logo-${useId().replace(/[^a-zA-Z0-9]/g, "")}`;
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
      <defs>
        <linearGradient id={gradId} x1="3" y1="2" x2="21" y2="22" gradientUnits="userSpaceOnUse">
          <stop style={{ stopColor: "rgb(var(--c-accent-fg))" }} />
          <stop offset="1" style={{ stopColor: "rgb(var(--c-accent))" }} />
        </linearGradient>
      </defs>
      <rect x="1" y="1" width="22" height="22" rx="6.4" fill={`url(#${gradId})`} />
      <g
        transform="translate(1.6 1.6) scale(.867)"
        style={{ stroke: "rgb(var(--c-on-accent))" }}
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M12 3v18" />
        <path d="M7.4 6.2c1.2 1 2.7 1.5 4.6 1.5s3.4-.5 4.6-1.5" />
        <path d="M12 19.4c4.2-1.1 4.2-4.2 0-4.9-4.2-.7-4.2-4 0-4.7" />
      </g>
    </svg>
  );
}

interface LockupProps {
  size?: number;
  className?: string;
}

/** Mark + wordmark, vertically centred. */
export function BrandLockup({ size = 24, className }: LockupProps) {
  return (
    <span className={`flex items-center gap-2.5 ${className ?? ""}`}>
      <Logo size={size} />
      <span className="text-[17px] font-semibold leading-none tracking-[-0.02em] text-ink">Asclepius</span>
    </span>
  );
}

export default Logo;
