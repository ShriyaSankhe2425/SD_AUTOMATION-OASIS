/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'sap-blue': '#0070d2',
        'sap-bg': '#f4f7f9',
        'sap-surface': '#ffffff',
        'sap-success': '#2b7d2b',
        'sap-warning': '#e9730c',
        'sap-error': '#bb0000',
      },
      fontFamily: {
        'inter': ['Inter', 'sans-serif'],
        'sans': ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      spacing: {
        '72': '4.5rem', // SAP 72 font spacing
      },
    },
  },
  plugins: [],
}
