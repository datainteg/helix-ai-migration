import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: ["Geist", "Inter", "-apple-system", "BlinkMacSystemFont", "system-ui", "sans-serif"],
        mono: ["Geist Mono", "JetBrains Mono", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      fontSize: {
        "2xs": ["10.5px", { lineHeight: "1.4" }],
        xs:   ["11.5px", { lineHeight: "1.45" }],
        sm:   ["12.5px", { lineHeight: "1.5" }],
        base: ["13.5px", { lineHeight: "1.5" }],
      },
      colors: {
        // Brand — preserved for backward compat with existing pages.
        helix: {
          50:  "#EEF0FF",
          100: "#E0E4FF",
          200: "#C5CCFE",
          300: "#9DA7FC",
          400: "#7681F8",
          500: "#4F46E5",
          600: "#4338CA",
          700: "#3730A3",
          800: "#312E81",
          900: "#1E1B4B",
        },
        violet: {
          500: "#8B5CF6",
          600: "#7C3AED",
        },
        cyan: {
          400: "#22D3EE",
          500: "#06B6D4",
        },
        // Console scale — drives the redesign. CSS-var backed so the tweaks
        // panel can override at runtime without rebuilding Tailwind.
        con: {
          bg:           "var(--con-bg)",
          "bg-2":       "var(--con-bg-2)",
          surface:      "var(--con-surface)",
          "surface-hi": "var(--con-surface-hi)",
          "ink-1":      "var(--con-ink-1)",
          "ink-2":      "var(--con-ink-2)",
          "ink-3":      "var(--con-ink-3)",
          "ink-4":      "var(--con-ink-4)",
          "ink-5":      "var(--con-ink-5)",
          line:         "var(--con-line)",
          "line-2":     "var(--con-line-2)",
          "line-3":     "var(--con-line-3)",
          brand:        "var(--con-brand)",
          ok:           "var(--con-ok)",
          warn:         "var(--con-warn)",
          err:          "var(--con-err)",
          info:         "var(--con-info)",
        },
        // Ink scale — backed by --con-ink-* CSS vars (see globals.css).
        // Contrast (vs --con-bg #FAFAF7):
        //   ink-1 21:1 · ink-2 12.6:1 · ink-3 7.2:1 · ink-4 4.55:1 · ink-5 4.5:1
        // ink-4 and ink-5 were bumped (from #8C8C86 / #B8B8B0) to meet WCAG AA
        // for any text that encodes information (em-dash "no data" cells,
        // metadata captions). Decorative use is fine at the prior shade — but
        // the rule is uniform so the tokens stay simple.
        ink: {
          DEFAULT: "var(--con-ink-1)",
          2: "var(--con-ink-2)",
          3: "var(--con-ink-3)",
          4: "var(--con-ink-4)",
          5: "var(--con-ink-5)",
        },
        surface: {
          DEFAULT: "var(--con-surface)",
          muted:   "var(--con-surface-hi)",
          subtle:  "var(--con-bg-2)",
        },
      },
      boxShadow: {
        xs:   "0 1px 0 rgba(10,10,10,0.04)",
        soft: "0 1px 2px rgba(10,10,10,0.04), 0 1px 1px rgba(10,10,10,0.03)",
        md:   "0 4px 12px -2px rgba(10,10,10,0.06), 0 1px 2px rgba(10,10,10,0.05)",
        lg:   "0 24px 48px -12px rgba(10,10,10,0.12), 0 4px 8px rgba(10,10,10,0.04)",
        glow: "0 4px 14px -2px rgba(79,70,229,0.40), 0 1px 2px rgba(79,70,229,0.20), inset 0 1px 0 rgba(255,255,255,0.20)",
        "glow-lg": "0 6px 20px -2px rgba(79,70,229,0.45), 0 1px 2px rgba(79,70,229,0.20), inset 0 1px 0 rgba(255,255,255,0.20)",
        hero: "0 30px 80px -20px rgba(15,23,42,0.25), 0 12px 30px -10px rgba(15,23,42,0.10)",
      },
      borderRadius: {
        DEFAULT: "8px",
        md: "8px",
        lg: "10px",
        xl: "12px",
        "2xl": "14px",
      },
      backgroundImage: {
        "indigo-violet": "linear-gradient(135deg, #8B5CF6 0%, #4F46E5 100%)",
        "indigo-cyan":   "linear-gradient(135deg, #4F46E5 0%, #06B6D4 100%)",
        "soft-indigo":   "linear-gradient(135deg, #F5F3FF 0%, #EEF0FF 100%)",
      },
      letterSpacing: {
        tight:    "-0.015em",
        tighter:  "-0.02em",
        editorial:"-0.025em",
      },
      keyframes: {
        "pulse-dot": {
          "0%, 100%": { opacity: "1" },
          "50%":      { opacity: "0.35" },
        },
      },
      animation: {
        "pulse-dot": "pulse-dot 1.6s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
