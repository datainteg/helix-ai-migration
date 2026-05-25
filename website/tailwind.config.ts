import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      colors: {
        ink: {
          DEFAULT: "#0A0A0A",
          2: "#27272A",
          3: "#52525B",
          4: "#71717A",
          5: "#A1A1AA",
        },
        surface: {
          DEFAULT: "#FFFFFF",
          muted:   "#FAFAF9",
          subtle:  "#F4F4F5",
        },
        brand: {
          50:  "#EEF2FF",
          100: "#E0E7FF",
          500: "#6366F1",
          600: "#4F46E5",
          700: "#4338CA",
          900: "#312E81",
        },
        cyan: {
          50:  "#ECFEFF",
          100: "#CFFAFE",
          200: "#A5F3FC",
          300: "#67E8F9",
          400: "#22D3EE",
          500: "#06B6D4",
          600: "#0891B2",
          700: "#0E7490",
          800: "#155E75",
          900: "#164E63",
        },
      },
      boxShadow: {
        soft: "0 1px 2px rgba(10,10,10,0.04), 0 1px 1px rgba(10,10,10,0.03)",
        md:   "0 4px 12px -2px rgba(10,10,10,0.06), 0 1px 2px rgba(10,10,10,0.05)",
        lg:   "0 24px 48px -12px rgba(10,10,10,0.12), 0 4px 8px rgba(10,10,10,0.04)",
        hero: "0 30px 80px -20px rgba(15,23,42,0.25), 0 12px 30px -10px rgba(15,23,42,0.10)",
      },
      borderRadius: {
        DEFAULT: "10px",
        xl: "14px",
        "2xl": "18px",
      },
      backgroundImage: {
        "indigo-cyan":   "linear-gradient(135deg, #4F46E5 0%, #06B6D4 100%)",
        "soft-indigo":   "linear-gradient(135deg, #F5F3FF 0%, #EEF0FF 100%)",
        "grid-faint":    "linear-gradient(rgba(10,10,10,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(10,10,10,0.04) 1px, transparent 1px)",
      },
    },
  },
  plugins: [],
};

export default config;
