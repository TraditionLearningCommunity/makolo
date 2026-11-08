/* Shared interaction layer: disclosure menus only, no owner-domain mutations.
 * Screen code supplies permitted actions as ordinary buttons, links or forms.
 * Works with server HTML and HTMX swaps through event delegation.
 */
(() => {
  'use strict';

  const rootSelector = '[data-mk-action-menu]';
  const triggerSelector = '[data-mk-action-trigger]';
  const panelSelector = '[data-mk-action-panel]';

  const isAvailable = (item) =>
    item.matches('a[href], button:not(:disabled), [role="menuitem"]:not([aria-disabled="true"])') &&
    item.getAttribute('aria-disabled') !== 'true' &&
    !item.hasAttribute('hidden');

  const items = (panel) =>
    Array.from(panel.querySelectorAll('.mk-action-item')).filter(isAvailable);

  const menuParts = (element) => {
    const root = element?.closest(rootSelector);
    if (!root) return null;
    const trigger = root.querySelector(triggerSelector);
    const panel = root.querySelector(panelSelector);
    if (!trigger || !panel || trigger.closest(rootSelector) !== root ||
        panel.closest(rootSelector) !== root) return null;
    return { root, trigger, panel };
  };

  function close(parts, restoreFocus = false) {
    if (parts.panel.hidden) return;
    parts.panel.hidden = true;
    parts.trigger.setAttribute('aria-expanded', 'false');
    if (restoreFocus && parts.trigger.isConnected) parts.trigger.focus();
  }

  function open(parts, focus = true) {
    document.querySelectorAll(rootSelector).forEach((menu) => {
      if (menu === parts.root) return;
      const other = menuParts(menu);
      if (other) close(other);
    });
    parts.panel.hidden = false;
    parts.trigger.setAttribute('aria-expanded', 'true');
    if (focus) (items(parts.panel)[0] || parts.trigger).focus();
  }

  function navigate(parts, direction, toEdge = false) {
    const actions = items(parts.panel);
    if (!actions.length) return;
    const position = actions.indexOf(document.activeElement);
    const next = toEdge
      ? (direction > 0 ? 0 : actions.length - 1)
      : (position + direction + actions.length) % actions.length;
    actions[next].focus();
  }

  document.addEventListener('click', (event) => {
    const trigger = event.target.closest(triggerSelector);
    if (trigger) {
      const parts = menuParts(trigger);
      if (!parts || parts.trigger !== trigger) return;
      event.preventDefault();
      if (parts.panel.hidden) open(parts);
      else close(parts, true);
      return;
    }
    const action = event.target.closest('.mk-action-item');
    if (action) {
      const parts = menuParts(action);
      if (parts && parts.panel.contains(action) && !parts.panel.hidden) {
        if (!isAvailable(action)) {
          event.preventDefault();
          return;
        }
        // Never prevent a native form submit or link navigation.
        close(parts);
        return;
      }
    }
    document.querySelectorAll(rootSelector).forEach((menu) => {
      if (menu.contains(event.target)) return;
      const parts = menuParts(menu);
      if (parts) close(parts);
    });
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      let closed = false;
      document.querySelectorAll(rootSelector).forEach((menu) => {
        const parts = menuParts(menu);
        if (parts && !parts.panel.hidden) {
          close(parts, true);
          closed = true;
        }
      });
      if (closed) {
        event.preventDefault();
        event.stopPropagation();
      }
      return;
    }
    const parts = menuParts(event.target);
    if (!parts) return;

    if (event.target === parts.trigger && ['ArrowDown', 'ArrowUp'].includes(event.key)) {
      event.preventDefault();
      open(parts, false);
      navigate(parts, event.key === 'ArrowDown' ? 1 : -1, true);
      return;
    }
    if (parts.panel.hidden || !parts.panel.contains(event.target)) return;
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      navigate(parts, event.key === 'ArrowDown' ? 1 : -1);
    } else if (event.key === 'Home' || event.key === 'End') {
      event.preventDefault();
      navigate(parts, event.key === 'Home' ? 1 : -1, true);
    } else if (event.key === 'Tab') {
      close(parts);
    }
  });

  document.addEventListener('focusin', (event) => {
    document.querySelectorAll(rootSelector).forEach((menu) => {
      if (menu.contains(event.target)) return;
      const parts = menuParts(menu);
      if (parts) close(parts);
    });
  });

  // Readable from E2E tests; no globally writable state or mutation transport.
  window.MakoloActionMenu = Object.freeze({ closeAll() {
    document.querySelectorAll(rootSelector).forEach((menu) => {
      const parts = menuParts(menu);
      if (parts) close(parts);
    });
  } });
})();
