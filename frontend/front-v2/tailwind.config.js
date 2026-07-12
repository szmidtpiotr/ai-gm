/** @type {import('tailwindcss').Config} */
// ŻAR design tokens — źródło prawdy: frontend_design.md sekcja 6.
// Kolory referują CSS vars w :root (src/index.css) — zero hardkodowanych hexów w komponentach.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        surface: "var(--surface)",
        "gm-bubble": "var(--gm-bubble)",
        "player-card": "var(--player-card)",
        "mech-card": "var(--mech-card)",
        inset: "var(--inset)",

        text: "var(--text)",
        "text-2": "var(--text-2)",
        "text-3": "var(--text-3)",

        ember: "var(--ember)",
        "ember-glow": "var(--ember-glow)",
        gold: "var(--gold)",
        "gold-glow": "var(--gold-glow)",
        success: "var(--success)",
        "mech-ok": "var(--mech-ok)",
        danger: "var(--danger)",
        "danger-glow": "var(--danger-glow)",
        mana: "var(--mana)",
        rare: "var(--rare)",
        epic: "var(--epic)",
      },
      borderColor: {
        DEFAULT: "var(--line)",
        line: "var(--line)",
        "line-soft": "var(--line-soft)",
        "line-ember": "var(--line-ember)",
        "line-mech": "var(--line-mech)",
        "line-danger": "var(--line-danger)",
      },
      fontFamily: {
        serif: "var(--font-serif)",
        ui: "var(--font-ui)",
        mono: "var(--font-mono)",
        sans: "var(--font-ui)",
      },
      fontSize: {
        micro: ["11px", "1.4"],
        label: ["13px", "1.4"],
        body: ["15px", "1.55"],
        prose: ["16px", "1.7"],
        "prose-lg": ["17px", "1.7"],
        title: ["18px", "1.3"],
        "title-lg": ["22px", "1.25"],
        "title-xl": ["27px", "1.2"],
      },
      borderRadius: {
        sm: "var(--r-sm)",
        md: "var(--r-md)",
        lg: "var(--r-lg)",
        xl: "var(--r-xl)",
        pill: "var(--r-pill)",
      },
      spacing: {
        1.5: "6px",
      },
      boxShadow: {
        float: "var(--shadow-float)",
        modal: "var(--shadow-modal)",
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "slide-up": {
          from: { transform: "translateY(100%)" },
          to: { transform: "translateY(0)" },
        },
        "slide-in-right": {
          from: { transform: "translateX(100%)" },
          to: { transform: "translateX(0)" },
        },
        "ember-flash": {
          "0%": { boxShadow: "0 0 0 0 var(--line-ember)" },
          "100%": { boxShadow: "0 0 0 8px rgba(255,122,61,0)" },
        },
      },
      animation: {
        "fade-in": "fade-in .18s ease-out",
        "slide-up": "slide-up .24s cubic-bezier(.22,1,.36,1)",
        "slide-in-right": "slide-in-right .24s cubic-bezier(.22,1,.36,1)",
        "ember-flash": "ember-flash .6s ease-out",
      },
    },
  },
  plugins: [],
};
