import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ss: {
          navy:         "#253043",
          "navy-dark":  "#1A2433",
          "navy-deep":  "#0F1623",
          "navy-soft":  "#3D4858",
          teal:         "#4A9CA6",  // official brand teal from logo SVG
          "teal-bright":"#5DACB6",
          "teal-deep":  "#3A8290",
          "teal-soft":  "#DCEFF1",
          cyan:         "#B1EAF8",
          "cyan-soft":  "#E7F7FC",
          cream:        "#F4FBFD",
          white:        "#FFFFFF",
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
