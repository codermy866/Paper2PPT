/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#1677ff",
          hover: "#4096ff",
          active: "#0958d9",
        },
        sidebar: {
          bg: "#0f2744",
          active: "#1677ff",
          muted: "#8ba3c0",
        },
      },
      borderRadius: {
        card: "8px",
      },
      boxShadow: {
        card: "0 1px 2px 0 rgb(0 0 0 / 0.05), 0 1px 3px 0 rgb(0 0 0 / 0.08)",
      },
    },
  },
  plugins: [],
};
