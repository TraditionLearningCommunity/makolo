/* Now N2 is a native presentation of the same owner facts, not a new route. */
(() => {
  "use strict";
  const root = document.getElementById("now-n2-layout");
  const focus = document.getElementById("now-n2-focus");
  const body = document.getElementById("now-n2-content");
  const close = document.getElementById("now-n2-close");
  if (!root || !focus || !body || !close) return;
  if (root.dataset.n2Bound === "1") return;
  root.dataset.n2Bound = "1";

  let activeKey = null;
  let sourceButton = null;
  let previousScroll = 0;

  const templateFor = (key) => Array.from(
    root.querySelectorAll("template[data-now-focus]")
  ).find((element) => element.dataset.nowFocus === key);

  function focusStart() {
    if (window.matchMedia("(max-width: 959px)").matches) {
      window.scrollTo({ top: 0, behavior: "instant" });
    }
    body.focus({ preventScroll: true });
  }

  function openN2(key, trigger) {
    const template = templateFor(key);
    if (!template?.content?.firstElementChild) return;
    if (!activeKey) previousScroll = window.scrollY;
    sourceButton = trigger;
    activeKey = key;
    body.replaceChildren(template.content.cloneNode(true));
    focus.hidden = false;
    root.classList.add("is-focused");
    root.querySelectorAll("[data-now-focus-trigger]").forEach((button) => {
      const selected = button.dataset.nowFocusTrigger === key;
      button.setAttribute("aria-expanded", String(selected));
    });
    requestAnimationFrame(focusStart);
  }

  function closeN2() {
    if (activeKey == null) return;
    activeKey = null;
    body.replaceChildren();
    focus.hidden = true;
    root.classList.remove("is-focused");
    root.querySelectorAll("[data-now-focus-trigger]").forEach((button) => {
      button.setAttribute("aria-expanded", "false");
    });
    if (window.matchMedia("(max-width: 959px)").matches) {
      window.scrollTo({ top: previousScroll, behavior: "instant" });
    }
    if (sourceButton?.isConnected) sourceButton.focus({ preventScroll: true });
    sourceButton = null;
  }

  root.addEventListener("click", (event) => {
    const trigger = event.target.closest("[data-now-focus-trigger]");
    if (!(trigger instanceof HTMLButtonElement) || !root.contains(trigger)) return;
    event.preventDefault();
    const key = trigger.dataset.nowFocusTrigger;
    if (key) openN2(key, trigger);
  });
  close.addEventListener("click", closeN2);
  root.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && activeKey != null) {
      event.preventDefault();
      closeN2();
    }
  });
  window.addEventListener("popstate", () => {
    if (activeKey != null) closeN2();
  });
})();
