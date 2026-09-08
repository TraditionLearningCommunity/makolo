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
  // replace historical Home/dashboard markup. These utilities remain safe to
  // retire only in a dedicated frontend artifact cleanup.
  safelist: [
    'py-11', 'sm:grid-cols-[70px_1fr_auto]', 'xl:col-span-4',
    'mx-auto', 'max-w-4xl', 'space-y-6', 'pb-10', 'mt-2', 'mt-3',
    'p-5', 'sm:p-6', 'flex', 'items-center', 'justify-between', 'gap-4',
    'text-lg', 'text-xs', 'mt-4', 'space-y-3', 'block', 'rounded-2xl',
    'border', 'p-4', 'items-start', 'min-w-0', 'font-bold', 'mt-1',
    'text-sm', 'font-semibold', 'py-7', 'text-center', 'overflow-hidden',
    'border-b', 'px-5', 'py-4', 'sm:px-6', 'last:border-b-0', 'px-6',
    'py-8', 'flex-wrap', 'grid', 'gap-3', 'sm:grid-cols-3', 'sm:px-7',
    'sm:py-9', 'text-2xl', 'tracking-[-.04em]', 'max-w-2xl', 'h-4',
    'w-4', 'mt-5',
  ],
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
