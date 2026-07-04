import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        idbi: {
          blue: "#003B73",
          deep: "#00264A",
          ocean: "#0A6EBD",
          light: "#E6F0FA",
          orange: "#F7931E",
          amber: "#FFB347",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "Segoe UI", "sans-serif"],
      },
    },
  },
  plugins: [],
};
export default config;