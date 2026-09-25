(() => {
  const EXPANDED_QUERY = '(min-width: 1200px)';
  const palette = () => document.getElementById('mk-command-palette');
  const input = () => document.getElementById('mk-command-input');
  const results = () => document.getElementById('mk-command-results');
  const status = () => document.getElementById('mk-command-status');
  let previousFocus = null;
  let commands = [];
  let activeIndex = 0;

  function isExpanded() {
    return window.matchMedia(EXPANDED_QUERY).matches;
  }

  function isTypingTarget(target) {
    if (!target) return false;
    const tag = target.tagName;
    return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target.isContentEditable;
  }

  function collectCommands() {
    const seen = new Set();
    const anchors = [
      ...document.querySelectorAll('#desktop-sidebar a[href]'),
      ...document.querySelectorAll('#app-topbar a[href][data-mk-command-source]'),
    ];
    return anchors.flatMap((anchor) => {
      const href = anchor.getAttribute('href');
      const label = (anchor.getAttribute('aria-label') || anchor.textContent || '').replace(/\s+/g, ' ').trim();
      if (!href || !label || href === '#' || seen.has(href)) return [];
      seen.add(href);
      return [{ label, href, anchor }];
    });
  }

  function filteredCommands(query) {
    const needle = (query || '').trim().toLocaleLowerCase('fr');
    if (!needle) return commands;
    return commands.filter((command) => command.label.toLocaleLowerCase('fr').includes(needle));
  }

  function render() {
    const list = results();
    const field = input();
    if (!list || !field) return;
    const filtered = filteredCommands(field.value);
    activeIndex = Math.min(activeIndex, Math.max(filtered.length - 1, 0));
    list.replaceChildren();

    filtered.forEach((command, index) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'mk-command-option';
      button.setAttribute('role', 'option');
      button.setAttribute('aria-selected', index === activeIndex ? 'true' : 'false');
      button.dataset.commandIndex = String(index);
      button.innerHTML = '<span></span><kbd>↵</kbd>';
      button.querySelector('span').textContent = command.label;
      button.addEventListener('click', () => activate(command));
      list.appendChild(button);
    });

    if (!filtered.length) {
      const empty = document.createElement('p');
      empty.className = 'mk-command-empty';
      empty.textContent = 'Aucune destination correspondante.';
      list.appendChild(empty);
    }

    const live = status();
    if (live) live.textContent = filtered.length ? `${filtered.length} destination${filtered.length > 1 ? 's' : ''}` : 'Aucun résultat';
  }

  function syncActiveOption() {
    const list = results();
    if (!list) return;
    const options = [...list.querySelectorAll('[role="option"]')];
    options.forEach((option, index) => option.setAttribute('aria-selected', index === activeIndex ? 'true' : 'false'));
    options[activeIndex]?.scrollIntoView({ block: 'nearest' });
  }

  function activate(command) {
    close();
    if (command.anchor && document.contains(command.anchor)) {
      command.anchor.click();
      return;
    }
    window.location.assign(command.href);
  }

  function open({ help = false } = {}) {
    if (!isExpanded()) return;
    const root = palette();
    const field = input();
    if (!root || !field) return;
    previousFocus = document.activeElement;
    commands = collectCommands();
    activeIndex = 0;
    root.hidden = false;
    root.dataset.mode = help ? 'help' : 'commands';
    field.value = '';
    field.placeholder = help ? 'Rechercher une destination ou consulter les raccourcis…' : 'Aller à…';
    render();
    window.requestAnimationFrame(() => field.focus());
  }

  function close() {
    const root = palette();
    if (!root || root.hidden) return;
    root.hidden = true;
    if (previousFocus && typeof previousFocus.focus === 'function') previousFocus.focus();
    previousFocus = null;
  }

  function move(delta) {
    const filtered = filteredCommands(input()?.value || '');
    if (!filtered.length) return;
    activeIndex = (activeIndex + delta + filtered.length) % filtered.length;
    syncActiveOption();
  }

  function activateCurrent() {
    const filtered = filteredCommands(input()?.value || '');
    if (filtered[activeIndex]) activate(filtered[activeIndex]);
  }

  document.addEventListener('click', (event) => {
    if (event.target.closest('[data-mk-command-trigger]')) {
      event.preventDefault();
      open();
      return;
    }
    if (event.target.closest('[data-mk-command-close]')) {
      event.preventDefault();
      close();
      return;
    }
    const root = palette();
    if (root && !root.hidden && event.target === root) close();
  });

  document.addEventListener('input', (event) => {
    if (event.target === input()) {
      activeIndex = 0;
      render();
    }
  });

  document.addEventListener('keydown', (event) => {
    const root = palette();
    const opened = root && !root.hidden;

    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      opened ? close() : open();
      return;
    }

    if (!opened && event.key === '?' && !event.metaKey && !event.ctrlKey && !event.altKey && !isTypingTarget(event.target)) {
      event.preventDefault();
      open({ help: true });
      return;
    }

    if (!opened) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      close();
    } else if (event.key === 'ArrowDown') {
      event.preventDefault();
      move(1);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      move(-1);
    } else if (event.key === 'Enter' && event.target === input()) {
      event.preventDefault();
      activateCurrent();
    }
  });
})();
