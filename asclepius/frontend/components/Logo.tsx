import { useId } from "react";
import { LOGO_FULL, LOGO_TINY, type LogoGeometry } from "@/components/logo-paths";

interface LogoProps {
  size?: number;
  className?: string;
}

const INK = "rgb(var(--c-on-accent))";

/**
 * The Asclepius mark: the Rod of Asclepius, a serpent coiled around a staff, drawn dark on a tile
 * filled with the theme's accent gradient. It is the ONLY brand mark in the app (sidebar, landing,
 * headers, favicon) and takes its colours from the active theme.
 *
 * Large sizes get the full serpent (belly plates, tongue); small sizes get a heavier, simpler cut so
 * the silhouette still reads as a snake on a staff.
 */
export function Logo({ size = 24, className }: LogoProps) {
  const id = `logo-${useId().replace(/[^a-zA-Z0-9]/g, "")}`;
  const detailed = size >= 40;
  const g: LogoGeometry = size >= 30 ? LOGO_FULL : LOGO_TINY;
  const staffW = size >= 30 ? 4.2 : 5.6;
  const knob = size >= 30 ? 2.7 : 3.3;
  const staffX = 32;

  return (
    <svg width={size} height={size} viewBox="0 0 64 64" fill="none" className={className} aria-hidden="true">
      <defs>
        <linearGradient id={id} x1="8" y1="4" x2="56" y2="60" gradientUnits="userSpaceOnUse">
          <stop style={{ stopColor: "rgb(var(--c-accent-hi))" }} />
          <stop offset="1" style={{ stopColor: "rgb(var(--c-accent))" }} />
        </linearGradient>
        <clipPath id={`${id}c`}>
          <rect x={staffX - 7.5} y="0" width="15" height="64" />
        </clipPath>
      </defs>
      <rect x="2" y="2" width="60" height="60" rx="16" fill={`url(#${id})`} />

      {/* passes behind the staff */}
      {g.back.map((d, i) => (
        <path key={`b${i}`} d={d} fill={INK} />
      ))}

      {/* the staff */}
      <rect x={staffX - staffW / 2} y="8" width={staffW} height="49" rx={staffW / 2} fill={INK} />
      <circle cx={staffX} cy="8" r={knob} fill={INK} />

      {/* a gap in the tile gradient lifts the in-front passes and the head off the staff */}
      <g clipPath={`url(#${id}c)`} fill={`url(#${id})`}>
        {g.frontHalo.map((d, i) => (
          <path key={`h${i}`} d={d} />
        ))}
        <path d={g.headHalo} />
      </g>

      {/* passes in front of the staff, then the head */}
      {g.front.map((d, i) => (
        <path key={`f${i}`} d={d} fill={INK} />
      ))}
      <path d={g.head} fill={INK} />

      {detailed && (
        <>
          <path
            d={g.scales}
            style={{ stroke: "rgb(var(--c-accent-hi))" }}
            strokeOpacity=".42"
            strokeWidth=".65"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path d={g.tongue} style={{ stroke: INK }} strokeWidth=".95" strokeLinecap="round" strokeLinejoin="round" />
        </>
      )}
      <circle cx={g.eye[0]} cy={g.eye[1]} r={detailed ? 1 : 1.2} style={{ fill: "rgb(var(--c-accent-hi))" }} />
    </svg>
  );
}

interface LockupProps {
  size?: number;
  className?: string;
}

/** Mark + wordmark, vertically centred. */
export function BrandLockup({ size = 26, className }: LockupProps) {
  return (
    <span className={`flex items-center gap-2.5 ${className ?? ""}`}>
      <Logo size={size} />
      <span className="text-[17px] font-semibold leading-none tracking-[-0.02em] text-ink">Asclepius</span>
    </span>
  );
}

export default Logo;
