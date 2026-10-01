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

function bindFirstPartyInteractions() {
  document.addEventListener('click', event => {
    const trigger = event.target.closest('[data-fill-target][data-fill-value]');
    if (!trigger) return;
    const target = document.getElementById(trigger.dataset.fillTarget || '');
    if (!target) return;
    target.value = trigger.dataset.fillValue || '';
    target.dispatchEvent(new Event('input', { bubbles: true }));
    target.focus();
  });

  document.addEventListener('submit', event => {
    const form = event.target.closest('form[data-confirm-message]');
    if (!form) return;
    const message = form.dataset.confirmMessage || 'Confirmer cette action ?';
    if (!window.confirm(message)) event.preventDefault();
  });
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
bindFirstPartyInteractions();

Alpine.start();
