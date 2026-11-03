/* Now N1: owner-scoped server pages, loaded when the final unit approaches. */
(() => {
  "use strict";
  const footer = document.getElementById("now-infinite");
  const stream = document.getElementById("now-stream");
  const status = document.getElementById("now-infinite-status");
  if (!footer || !stream || !status) return;
  const gate = footer;
  if (gate.dataset.autoloadBound === "1") return;
  gate.dataset.autoloadBound = "1";

  let loading = false;
  let failed = false;
  let generation = 0;
  let observer;

  function setStatus(message) {
    status.textContent = message;
  }

  function finished() {
    footer.dataset.state = "end";
    footer.dataset.nextToken = "";
    setStatus("Vous avez tout exploré");
    observer?.disconnect();
  }

  function retry() {
    if (footer.querySelector("button")) return;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "mk-now-cta";
    button.textContent = "Réessayer";
    button.addEventListener("click", () => {
      button.remove();
      failed = false;
      void loadMore();
    }, { once: true });
    footer.appendChild(button);
  }

  async function loadMore() {
    const token = footer.dataset.nextToken || "";
    if (loading || failed || footer.dataset.state !== "more" || !token) return;
    const requested = ++generation;
    loading = true;
    setStatus("Chargement…");
    try {
      const url = new URL(window.location.pathname, window.location.origin);
      url.searchParams.set("continuation", token);
      const response = await fetch(url.toString(), {
        credentials: "same-origin",
        cache: "no-store",
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          Accept: "text/html",
        },
      });
      if (!response.ok || response.redirected) throw new Error("Now unavailable");
      const documentFragment = new DOMParser().parseFromString(
        await response.text(), "text/html"
      );
      const batch = documentFragment.querySelector("[data-now-batch]");
      const state = batch?.dataset.continuationState;
      const next = batch?.dataset.nextToken || "";
      if (!batch || !["more", "end"].includes(state) ||
          (state === "more" && (!next || next === token))) {
        throw new Error("Invalid Now continuation");
      }
      if (requested !== generation) return;
      let inserted = 0;
      const existing = new Set(Array.from(
        document.querySelectorAll("[data-now-identity]"),
        (element) => element.dataset.nowIdentity
      ));
      for (const item of Array.from(batch.children)) {
        const id = item.dataset.nowIdentity;
        if (!id || existing.has(id)) continue;
        existing.add(id);
        stream.appendChild(item);
        inserted += 1;
      }
      if (state === "more" && inserted === 0) {
        throw new Error("Now continuation stalled");
      }
      footer.dataset.state = state;
      footer.dataset.nextToken = next;
      if (state === "end") finished();
      else setStatus("");
    } catch (_) {
      failed = true;
      setStatus("La suite n’a pas pu être chargée.");
      retry();
    } finally {
      loading = false;
      if (!failed && footer.dataset.state === "more" &&
          footer.getBoundingClientRect().top < window.innerHeight + 500) {
        requestAnimationFrame(() => { void loadMore(); });
      }
    }
  }

  if (footer.dataset.state === "end") {
    finished();
    return;
  }
  if (!footer.dataset.nextToken) return;
  if (!("IntersectionObserver" in window)) {
    window.addEventListener("scroll", () => {
      if (footer.getBoundingClientRect().top < window.innerHeight + 500) {
        void loadMore();
      }
    }, { passive: true });
    void loadMore();
    return;
  }
  observer = new IntersectionObserver((entries) => {
    if (entries.some((entry) => entry.isIntersecting)) void loadMore();
  }, { rootMargin: "500px 0px" });
  observer.observe(footer);
})();
