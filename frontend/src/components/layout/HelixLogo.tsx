interface LogoProps {
  size?: number;
}

/**
 * Helix mark — a black rounded square with helix strands inside.
 * Used in the sidebar wordmark and as a small brand chip elsewhere.
 */
export function HelixLogo({ size = 24 }: LogoProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden>
      <rect x="0" y="0" width="24" height="24" rx="6" fill="#0A0A0A" />
      <path
        d="M7 6c0 5 10 6 10 12 M17 6c0 5-10 6-10 12 M7 9h10 M7 15h10"
        stroke="#FAFAF7"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

/**
 * Wordmark — logo + "Helix Console v0.4.2 · ENT".
 * Designed for the sidebar header.
 */
export function HelixWordmark({ size = 22 }: { size?: number }) {
  return (
    <div className="flex items-center gap-2">
      <HelixLogo size={size} />
      <div className="flex flex-col leading-none">
        <div className="text-[14px] font-semibold tracking-tight text-ink">
          Helix <span className="text-ink-4 font-medium">Console</span>
        </div>
        <div className="text-[9.5px] text-ink-4 mt-[3px] font-mono tracking-[0.05em]">
          v0.4.2 · ENT
        </div>
      </div>
    </div>
  );
}

/**
 * Decorative hero art kept for backward compat with PageHero.
 * Now renders nothing — calm operations aesthetic has no hero ribbon.
 */
export function HeroHelixArt(_props: { width?: number }) {
  return null;
}
