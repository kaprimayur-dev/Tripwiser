/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        cream: {
          50: '#FAF7F2',
          100: '#F4EFE4', // Primary Cream background
          200: '#E7E2D7',
          300: '#D8D2C4',
        },
        espresso: {
          900: '#191612', // Primary Espresso dark text
          800: '#2A2520',
          700: '#3D3630',
        },
        terracotta: {
          DEFAULT: '#B9532D', // Primary Terracotta accent
          hover: '#A34624',
          light: '#F5E8E2',
        },
        olive: {
          DEFAULT: '#67664A', // Muted Olive secondary accent
          hover: '#54533C',
          light: '#ECEBE4',
        }
      },
      fontFamily: {
        display: ['Space Grotesk', 'Cabinet Grotesk', 'system-ui', 'sans-serif'],
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
