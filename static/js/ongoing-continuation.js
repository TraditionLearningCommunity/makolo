/* En cours N1: auto continuation, native owner cards, no numbered pagination. */
(() => {
  "use strict";
  const sentinel = document.getElementById("ongoing-infinite");
  const stream = document.getElementById("ongoing-stream");
  const status = document.getElementById("ongoing-infinite-status");
  if (!sentinel || !stream || !status) return;
  let busy = false;
  let failed = false;
  let observer;

  const complete = () => {
    sentinel.dataset.state = "end";
    sentinel.dataset.nextToken = "";
    status.textContent = "Vous avez tout exploré";
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
      if (window.htmx?.process) window.htmx.process(stream);
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
