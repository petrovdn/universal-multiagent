/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'agent-message': '#3b82f6',
        'user-message': '#10b981',
      },
    },
  },
  plugins: [],
  darkMode: 'class',
}



