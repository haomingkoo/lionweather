/** @type {import('tailwindcss').Config} */
const token = (name) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Tokens defined in src/index.css; values swap between day and night.
        bg: token("bg"),
        surface: { DEFAULT: token("surface"), 2: token("surface-2") },
        line: token("line"),
        ink: token("ink"),
        muted: token("muted"),
        accent: { DEFAULT: token("accent"), ink: token("accent-ink") },
        rain: token("rain"),
        good: token("good"),
        warn: token("warn"),
        bad: token("bad"),
      },
      borderRadius: {
        control: "6px",
        card: "10px",
        panel: "16px",
      },
    },
  },
  plugins: [],
};
