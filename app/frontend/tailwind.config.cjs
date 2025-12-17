/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "#0b1021",
        surface: "#0f172a",
        panel: "#0b1221",
        border: "#1f2937",
        accent: {
          blue: "#3b82f6",
          teal: "#14b8a6"
        }
      },
      boxShadow: {
        deep: "0 10px 40px rgba(0,0,0,0.35)"
      },
      borderRadius: {
        xl: "16px"
      }
    }
  },
  plugins: []
};
