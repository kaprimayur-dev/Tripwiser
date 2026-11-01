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
          100: '#F4EFE4', // Primary Archival Cream canvas
          200: '#EAE4D5', // Elevated surface
          300: '#D8D1BF', // Ledger border rule
        },
        espresso: {
          900: '#191612', // Primary dark text
          800: '#2A2520',
          700: '#3D3630',
          600: '#564F44', // Secondary muted umber text
          500: '#756F65',
        },
        terracotta: {
          DEFAULT: '#B9532D', // Primary Terracotta accent
          hover: '#A34624',
          light: '#FDF2ED',
        },
        olive: {
          DEFAULT: '#67664A', // Muted Olive secondary accent
          hover: '#54533C',
          light: '#ECEBE4',
        },
      },
      fontFamily: {
        display: ['var(--font-epilogue)', 'Epilogue', 'sans-serif'],
        sans: ['var(--font-plus-jakarta)', 'Plus Jakarta Sans', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
