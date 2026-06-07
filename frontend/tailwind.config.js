/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#1f2933",
        panel: "#f7f9fb",
        line: "#d8dee6",
        accent: "#2563eb",
        success: "#0f766e",
      },
      boxShadow: {
        surface: "0 12px 32px rgba(31, 41, 51, 0.08)",
      },
    },
  },
  plugins: [],
};
