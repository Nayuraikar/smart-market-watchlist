/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        groww: {
          green: '#00B386',
          'green-dark': '#009670',
          'green-light': '#E6F7F3',
          red: '#EB5757',
          'red-dark': '#C53030',
          'red-light': '#FDF2F2',
          navy: '#0B192C',
          'navy-light': '#1E293B',
          bg: '#F4F6F8',
          card: '#FFFFFF',
          border: '#E2E8F0',
          muted: '#64748B',
          dark: '#0F172A',
        },
      },
      fontFamily: {
        sans: ['Manrope', 'Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
      boxShadow: {
        'card-subtle': '0 1px 3px 0 rgba(0, 0, 0, 0.04), 0 1px 2px 0 rgba(0, 0, 0, 0.02)',
        'card-hover': '0 4px 12px -2px rgba(0, 0, 0, 0.06), 0 2px 6px -1px rgba(0, 0, 0, 0.03)',
        'glow-green': '0 0 12px 0 rgba(0, 179, 134, 0.2)',
      },
    },
  },
  plugins: [],
}
