import Alpine from '@alpinejs/csp';
import htmx from 'htmx.org';
import { createIcons } from 'lucide';
import { makoloIcons } from '../.generated/lucide-icons.js';

const root = document.documentElement;

function preferredDark() {
  const stored = localStorage.getItem('theme');
  if (stored === 'dark') return true;
  if (stored === 'light') return false;
  return Boolean(window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
}

function refreshIcons() {
  createIcons({ icons: makoloIcons });
}

window.htmx = htmx;
window.lucide = { createIcons: refreshIcons, icons: makoloIcons };
window.Alpine = Alpine;

Alpine.data('themeManager', () => ({
  dark: preferredDark(),
  init() {
    this.applyTheme();
  },
  toggleTheme() {
    this.dark = !this.dark;
    localStorage.setItem('theme', this.dark ? 'dark' : 'light');
    this.applyTheme();
  },
  applyTheme() {
    root.classList.toggle('dark', this.dark);
    root.style.colorScheme = this.dark ? 'dark' : 'light';
  },
}));

document.addEventListener('DOMContentLoaded', refreshIcons);
document.addEventListener('htmx:afterSwap', refreshIcons);
document.addEventListener('htmx:afterSettle', refreshIcons);
document.addEventListener('alpine:initialized', refreshIcons);

Alpine.start();
