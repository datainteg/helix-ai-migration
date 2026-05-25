export function BrandMark({ className = "h-8 w-8 rounded-lg" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center justify-center ${className}`}>
      <svg viewBox="0 0 32 32" className="h-full w-full" role="img" aria-label="Helix logo">
        <defs>
          <linearGradient id="helixGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#4F46E5" />
            <stop offset="100%" stopColor="#06B6D4" />
          </linearGradient>
        </defs>
        <rect width="32" height="32" rx="8" fill="url(#helixGradient)" />
        <path d="M8 10h4v4h8v-4h4v12h-4v-4h-8v4H8V10z" fill="#ffffff" />
      </svg>
    </span>
  );
}
