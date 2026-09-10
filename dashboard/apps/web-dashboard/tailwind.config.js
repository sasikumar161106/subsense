/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        mining: {
          950: "#090d16",
          900: "#0f172a",
          850: "#131d35",
          800: "#1e293b",
          700: "#334155",
          amber: "#f59e0b",
          critical: "#ef4444",
          nominal: "#10b981",
          cyan: "#06b6d4",
        },
      },
      fontFamily: {
        mono: ["JetBrains Mono", "SFMono-Regular", "Menlo", "Monaco", "Consolas", "monospace"],
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "sans-serif"],
      },
      animation: {
        "pulse-fast": "pulse 1s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "beacon": "beacon 2s cubic-bezier(0, 0, 0.2, 1) infinite",
      },
      keyframes: {
        beacon: {
          "0%": { transform: "scale(0.95)", opacity: "0.8" },
          "50%": { transform: "scale(1.4)", opacity: "0" },
          "100%": { transform: "scale(0.95)", opacity: "0" },
        },
      },
    },
  },
  plugins: [],
};
