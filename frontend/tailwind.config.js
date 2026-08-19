/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './templates/**/*.html',
    './{accounts,analytics_app,automation,crm,discovery,events,growth,loyalty,notifications,operations,organizations,partners,payments,promotions,scanner,tickets}/templates/**/*.html',
    './frontend/src/**/*.js',
    './static/js/**/*.js',
  ],
  // Keep the committed production bundle stable while participant surfaces
  // replace the historical dashboard that used these responsive utilities.
  safelist: ['py-11', 'sm:grid-cols-[70px_1fr_auto]', 'xl:col-span-4'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
        heading: ['Manrope', 'Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
      },
      colors: {
        primary: '#5232DB',
        secondary: '#2B176E',
        accent: '#FF704D',
        ink: '#0F172A',
        warm: '#FFF8F3',
        success: '#07806F',
        warning: '#B45309',
        danger: '#C83C3C',
        info: '#2563EB',
      },
      boxShadow: {
        soft: '0 1px 2px rgba(15,23,42,.035), 0 8px 22px rgba(15,23,42,.035)',
      },
    },
  },
  plugins: [],
};
