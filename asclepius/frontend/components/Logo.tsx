interface GlyphProps {
  size?: number;
  color?: string;
  bg?: string;
  className?: string;
}

/**
 * Helix brand mark: a three-node graph triangle. Three propositions
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
  className?: string;
}

/** Glyph + "Asclepius" wordmark, vertically centered. */
export function BrandLockup({ size = 26, className }: LockupProps) {
  return (
    <span className={`flex items-center gap-3 ${className ?? ""}`}>
      <Logo size={size} />
      <span className="font-sans font-semibold leading-none text-ink tracking-tight" style={{ fontSize: 22 }}>
        Asclepius
      </span>
    </span>
  );
}

export default Logo;
