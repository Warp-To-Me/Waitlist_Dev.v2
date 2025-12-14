/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      colors: {
        // 1. DYNAMIC BRAND COLORS
        brand: {
          50: 'rgb(var(--brand-50) / <alpha-value>)',
          100: 'rgb(var(--brand-100) / <alpha-value>)',
          200: 'rgb(var(--brand-200) / <alpha-value>)',
          300: 'rgb(var(--brand-300) / <alpha-value>)',
          400: 'rgb(var(--brand-400) / <alpha-value>)',
          500: 'rgb(var(--brand-500) / <alpha-value>)',
          600: 'rgb(var(--brand-600) / <alpha-value>)',
          700: 'rgb(var(--brand-700) / <alpha-value>)',
          800: 'rgb(var(--brand-800) / <alpha-value>)',
          900: 'rgb(var(--brand-900) / <alpha-value>)',
          950: 'rgb(var(--brand-950) / <alpha-value>)',
        },
        // 2. OVERRIDE STANDARD COLORS WITH VARIABLES
        dark: {
          950: 'rgb(var(--c-dark-950) / <alpha-value>)', // Main BG
          900: 'rgb(var(--c-dark-900) / <alpha-value>)', // Panel BG
          800: 'rgb(var(--c-dark-800) / <alpha-value>)',
        },
        slate: {
          900: 'rgb(var(--c-slate-900) / <alpha-value>)',
          800: 'rgb(var(--c-slate-800) / <alpha-value>)',
          700: 'rgb(var(--c-slate-700) / <alpha-value>)',
          400: 'rgb(var(--c-slate-400) / <alpha-value>)', // Muted Text
          300: 'rgb(var(--c-slate-300) / <alpha-value>)', // Body Text
        },
        // Inverting white ensures headings are visible on light backgrounds
        white: 'rgb(var(--c-white) / <alpha-value>)',
      }
    },
  },
  plugins: [],
}