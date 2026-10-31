/* N2 continuity is a viewer-scoped presentation; N3 stays in the owner route. */
(() => {
  "use strict";
  const field = document.querySelector('[data-mk-surface="ongoing"]');
  const workspace = field?.closest(".mk-workspace");
  const panel = workspace?.querySelector("#ongoing-detail");
  const body = panel?.querySelector("#ongoing-detail-body");
  const close = panel?.querySelector("#ongoing-n2-close");
  if (!field || !workspace || !panel || !body || !close) return;
  if (field.dataset.n2Bound === "1") return;
  field.dataset.n2Bound = "1";

  let activeKey = null;
  let previousScroll = 0;
  let opener = null;

  const templateFor = (key) => Array.from(
    field.querySelectorAll("template[data-ongoing-focus]")
  ).find((item) => item.dataset.ongoingFocus === key);

  function openFocus(key, button) {
    const template = templateFor(key);
    if (!template?.content?.firstElementChild) return;
    if (activeKey == null) previousScroll = window.scrollY;
    activeKey = key;
    opener = button;
    body.replaceChildren(template.content.cloneNode(true));
    panel.hidden = false;
    workspace.classList.add("mk-ongoing-n2-active");
    field.querySelectorAll("[data-ongoing-focus-trigger]").forEach((trigger) => {
      trigger.setAttribute(
        "aria-expanded", String(trigger.dataset.ongoingFocusTrigger === key)
      );
    });
    if (window.matchMedia("(max-width: 959px)").matches) {
      window.scrollTo({ top: 0, behavior: "instant" });
    }
    requestAnimationFrame(() => body.focus({ preventScroll: true }));
  }

  function closeFocus() {
    if (activeKey == null) return;
    activeKey = null;
    panel.hidden = true;
    body.replaceChildren();
    workspace.classList.remove("mk-ongoing-n2-active");
    field.querySelectorAll("[data-ongoing-focus-trigger]").forEach((button) => {
      button.setAttribute("aria-expanded", "false");
    });
    if (window.matchMedia("(max-width: 959px)").matches) {
      window.scrollTo({ top: previousScroll, behavior: "instant" });
    }
    if (opener?.isConnected) opener.focus({ preventScroll: true });
    opener = null;
  }

  field.addEventListener("click", (event) => {
    const trigger = event.target.closest("[data-ongoing-focus-trigger]");
    if (!(trigger instanceof HTMLButtonElement)) return;
    const key = trigger.dataset.ongoingFocusTrigger;
    if (!key) return;
    event.preventDefault();
    openFocus(key, trigger);
  });
  close.addEventListener("click", closeFocus);
  workspace.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && activeKey != null) {
      event.preventDefault();
      closeFocus();
    }
  });
  window.addEventListener("popstate", () => {
    if (activeKey != null) closeFocus();
  });
})();
