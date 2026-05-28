interface GlyphProps {
  size?: number;
  color?: string;
  bg?: string;
  className?: string;
}

/**
 * Helix brand mark — a three-node graph triangle. Three propositions
 * connected by inference, the smallest unit of the platform. The single
 * outline node is the retrieval target.
 */
export function Logo({ size = 26, color = "#87f085", bg = "#0c1014", className }: GlyphProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 26 26" className={className} aria-hidden="true">
      <line x1="5" y1="20" x2="21" y2="20" stroke={color} strokeWidth="1.4" opacity="0.7" />
      <line x1="5" y1="20" x2="13" y2="5" stroke={color} strokeWidth="1.4" opacity="0.7" />
      <line x1="21" y1="20" x2="13" y2="5" stroke={color} strokeWidth="1.4" opacity="0.7" />
      <circle cx="5" cy="20" r="3" fill={color} />
      <circle cx="21" cy="20" r="3" fill={bg} stroke={color} strokeWidth="1.6" />
      <circle cx="13" cy="5" r="3" fill={color} />
    </svg>
  );
}

interface LockupProps {
  size?: number;
  showSub?: boolean;
  className?: string;
}

/** Glyph + "Asclepius" wordmark + "Research Intelligence" sub-label. */
export function BrandLockup({ size = 22, showSub = true, className }: LockupProps) {
  return (
    <span className={`flex items-center gap-2.5 ${className ?? ""}`}>
      <Logo size={size} />
      <span className="flex flex-col leading-none">
        <span className="font-sans font-semibold text-ink tracking-tight" style={{ fontSize: 15 }}>
          Asclepius
        </span>
        {showSub && (
          <span className="mt-1 font-mono uppercase text-muted" style={{ fontSize: 8, letterSpacing: "0.22em" }}>
            Research Intelligence
          </span>
        )}
      </span>
    </span>
  );
}

export default Logo;
