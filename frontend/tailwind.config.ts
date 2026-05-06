import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#1f2937",
        mist: "#edf4f2",
        salmon: "#f08a5d",
        spruce: "#1f6f78",
        sun: "#ffd166",
      },
      boxShadow: {
        panel: "0 24px 60px rgba(31, 41, 55, 0.14)",
      },
    },
  },
  plugins: [],
};

export default config;

