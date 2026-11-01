import { useId } from "react";
import { CADUCEUS_PATH, CADUCEUS_TRANSFORM } from "@/components/logo-paths";

interface LogoProps {
  size?: number;
  className?: string;
}

/**
 * The Asclepius mark: a winged staff with two interlaced serpents, drawn dark on a tile filled with the
 * theme's accent gradient. It is the ONLY brand mark in the app (sidebar, landing, headers, favicon) and
 * takes its colours from the active theme. Artwork: see logo-paths.ts and THIRD_PARTY_NOTICES.md.
 */
export function Logo({ size = 24, className }: LogoProps) {
  const id = `logo-${useId().replace(/[^a-zA-Z0-9]/g, "")}`;
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" fill="none" className={className} aria-hidden="true">
      <defs>
        <linearGradient id={id} x1="8" y1="4" x2="56" y2="60" gradientUnits="userSpaceOnUse">
          <stop style={{ stopColor: "rgb(var(--c-accent-hi))" }} />
          <stop offset="1" style={{ stopColor: "rgb(var(--c-accent))" }} />
        </linearGradient>
      </defs>
      <rect x="2" y="2" width="60" height="60" rx="16" fill={`url(#${id})`} />
      <path d={CADUCEUS_PATH} transform={CADUCEUS_TRANSFORM} style={{ fill: "rgb(var(--c-on-accent))" }} />
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
