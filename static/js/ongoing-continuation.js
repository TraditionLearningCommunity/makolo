/* En cours N1: auto continuation, native owner cards, no numbered pagination. */
(() => {
  "use strict";
  const sentinel = document.getElementById("ongoing-infinite");
  const stream = document.getElementById("ongoing-stream");
  const status = document.getElementById("ongoing-infinite-status");
  if (!sentinel || !stream || !status) return;
  const gate = sentinel;
  if (gate.dataset.autoloadBound === "1") return;
  gate.dataset.autoloadBound = "1";
  let busy = false;
  let failed = false;
  let observer;

  const calendar = document.getElementById("ongoing-calendar");
  const calendarList = document.getElementById("ongoing-calendar-moments");
  const calendarEmpty = document.getElementById("ongoing-calendar-empty");
  const renderCalendar = () => {
    if (!calendarList || !calendarEmpty) return;
    const moments = Array.from(stream.querySelectorAll("[data-ongoing-calendar-moment]"))
      .map((node) => ({
        sort: node.dataset.ongoingSort || "",
        when: node.dataset.ongoingWhen || "",
        label: node.dataset.ongoingLabel || "",
        title: node.dataset.ongoingTitle || "",
        target: node.dataset.ongoingTarget || "",
      }))
      .filter((item) => item.sort && item.when && item.target)
      .sort((a, b) => a.sort.localeCompare(b.sort) || a.title.localeCompare(b.title));
    calendarList.replaceChildren();
    const seen = new Set();
    for (const item of moments) {
      const key = [item.target, item.sort, item.label].join("|");
      if (seen.has(key)) continue;
      seen.add(key);
      const row = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "mk-compact-action";
      button.textContent = [item.when, item.title, item.label].filter(Boolean).join(" · ");
      button.addEventListener("click", () => {
        const trigger = Array.from(stream.querySelectorAll("[data-ongoing-focus-trigger]"))
          .find((node) => node.dataset.ongoingFocusTrigger === item.target);
        if (!trigger) return;
        if (calendar) calendar.open = false;
        trigger.click();
      });
      row.appendChild(button);
      calendarList.appendChild(row);
    }
    calendarEmpty.hidden = seen.size > 0;
  };
  renderCalendar();

  // Save belongs to Discovery. The same saved Activity can appear through
  // several independent personal continuities; update each visible control.
  stream.addEventListener("click", async (event) => {
    const button = event.target.closest?.("[data-ongoing-save-toggle]");
    if (!button) return;
    const form = button.closest("[data-ongoing-save]");
    if (!form || button.disabled || !form.dataset.saveUrl) return;
    button.disabled = true;
    const saved = form.dataset.saveState === "saved";
    const csrf = form.querySelector('input[name="csrfmiddlewaretoken"]')?.value || "";
    const feedback = form.querySelector("[data-ongoing-save-feedback]");
    try {
      const response = await fetch(form.dataset.saveUrl, {
        method: saved ? "DELETE" : "PUT",
        credentials: "same-origin",
        cache: "no-store",
        headers: {
          "X-CSRFToken": csrf,
          Accept: "application/json",
          "X-Requested-With": "XMLHttpRequest",
        },
      });
      if (!response.ok) throw new Error("Saving rejected");
      const payload = await response.json();
      if (payload?.projection !== "discovery.saved") {
        throw new Error("Invalid saved confirmation");
      }
      const state = saved ? "not_saved" : "saved";
      stream.querySelectorAll("[data-ongoing-save]").forEach((other) => {
        if (other.dataset.ongoingActivity !== form.dataset.ongoingActivity) return;
        other.dataset.saveState = state;
        const toggle = other.querySelector("[data-ongoing-save-toggle]");
        const label = other.querySelector("[data-ongoing-save-label]");
        if (toggle) toggle.setAttribute("aria-pressed", state === "saved" ? "true" : "false");
        if (label) label.textContent = state === "saved" ? "Enregistré" : "Enregistrer";
        const availableIcon = other.querySelector("[data-ongoing-orbit-available]");
        const savedIcon = other.querySelector("[data-ongoing-orbit-saved]");
        if (availableIcon) availableIcon.hidden = state === "saved";
        if (savedIcon) savedIcon.hidden = state !== "saved";
        if (toggle) toggle.title = state === "saved" ? "Enregistré" : "Enregistrer";
      });
      if (feedback) feedback.textContent = saved ? "Enregistrement retiré." : "Possibilité enregistrée.";
    } catch (_) {
      if (feedback) feedback.textContent = "Enregistrement non confirmé. Réessayez.";
    } finally {
      button.disabled = false;
    }
  });

  const complete = () => {
    sentinel.dataset.state = "end";
    sentinel.dataset.nextToken = "";
    status.textContent = "";
    observer?.disconnect();
  };

  const fetchMore = async () => {
    const token = sentinel.dataset.nextToken || "";
    if (busy || failed || sentinel.dataset.state !== "more" || !token) return;
    busy = true;
    status.textContent = "Chargement…";
    try {
      const url = new URL(window.location.pathname, window.location.origin);
      url.searchParams.set("continuation", token);
      const response = await fetch(url.toString(), {
        credentials: "same-origin",
        cache: "no-store",
        headers: { "X-Makolo-Continuation": "1", Accept: "text/html" },
      });
      if (!response.ok || response.redirected) throw new Error("Unavailable");
      const html = new DOMParser().parseFromString(await response.text(), "text/html");
      const batch = html.querySelector("[data-ongoing-batch]");
      const state = batch?.dataset.state;
      const next = batch?.dataset.nextToken || "";
      if (!batch || !["more", "end"].includes(state) ||
          (state === "more" && (!next || token === next))) {
        throw new Error("Invalid continuation");
      }
      const seen = new Set(Array.from(stream.querySelectorAll("[data-ongoing-unit]"),
        (element) => element.dataset.ongoingId));
      let count = 0;
      for (const element of Array.from(batch.children)) {
        if (!element.hasAttribute("data-ongoing-unit")) continue;
        const id = element.dataset.ongoingId;
        if (!id || seen.has(id)) continue;
        stream.appendChild(element);
        seen.add(id);
        count += 1;
      }
      if (state === "more" && count === 0) throw new Error("Stalled continuation");
      sentinel.dataset.state = state;
      sentinel.dataset.nextToken = next;
      renderCalendar();
      if (window.htmx?.process) window.htmx.process(stream);
      document.dispatchEvent(new CustomEvent("makolo:fragment-inserted", { detail: { scope: stream } }));
      if (window.lucide?.createIcons) window.lucide.createIcons({ attrs: { "stroke-width": 1.8 } });
      if (state === "end") complete();
      else status.textContent = "";
    } catch (_) {
      failed = true;
      status.textContent = "La suite n’a pas pu être chargée.";
      const retry = document.createElement("button");
      retry.type = "button";
      retry.className = "mk-compact-action";
      retry.textContent = "Réessayer";
      retry.addEventListener("click", () => {
        retry.remove();
        failed = false;
        void fetchMore();
      }, { once: true });
      sentinel.appendChild(retry);
    } finally {
      busy = false;
      if (!failed && sentinel.dataset.state === "more" &&
          sentinel.getBoundingClientRect().top < window.innerHeight + 480) {
        requestAnimationFrame(() => { void fetchMore(); });
      }
    }
  };

  if (sentinel.dataset.state === "end") { complete(); return; }
  if (!sentinel.dataset.nextToken) return;
  if ("IntersectionObserver" in window) {
    observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) void fetchMore();
    }, { rootMargin: "480px 0px" });
    observer.observe(sentinel);
  } else {
    window.addEventListener("scroll", () => {
      if (sentinel.getBoundingClientRect().top < window.innerHeight + 480) {
        void fetchMore();
      }
    }, { passive: true });
    void fetchMore();
  }
})();
