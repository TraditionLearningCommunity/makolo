/* Now presents owner-issued decisions; only the owner endpoint mutates. */
(() => {
  "use strict";
  const surface = document.querySelector('[data-mk-surface="now"]');
  if (!surface) return;

  surface.addEventListener("submit", async (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || !form.matches("[data-now-direct]")) {
      return;
    }
    event.preventDefault();
    if (form.dataset.sending === "true") return;
    const target = new URL(form.action, window.location.origin);
    // Never POST a cross-origin action, even if a malformed template leaks one.
    if (target.origin !== window.location.origin ||
        !target.pathname.startsWith("/api/v1/recognition/redemptions/")) {
      return;
    }
    const button = form.querySelector('button[type="submit"]');
    const feedback = form.querySelector("output");
    const token = form.querySelector('input[name="csrfmiddlewaretoken"]');
    if (!button || !feedback || !token) return;

    if (!window.confirm("Confirmer la décision « " + button.textContent.trim() + " » ?")) {
      return;
    }
    form.dataset.sending = "true";
    button.disabled = true;
    feedback.textContent = "Envoi de votre décision…";
    try {
      const response = await fetch(target.toString(), {
        method: "POST",
        credentials: "same-origin",
        cache: "no-store",
        redirect: "error",
        headers: {
          Accept: "application/json",
          "X-CSRFToken": token.value,
        },
      });
      const payload = await response.json();
      if (!response.ok || String(payload.id || "").toLowerCase() !==
          String(form.dataset.ownerId || "").toLowerCase()) {
        throw new Error("Owner confirmation missing");
      }
      feedback.textContent = "Décision confirmée par le propriétaire.";
      // Reproject Now from the server instead of rewriting business truth in JS.
      window.location.reload();
    } catch (_) {
      feedback.textContent =
        "Cette décision n’a pas été confirmée. Vérifiez son état dans la démarche.";
      button.disabled = false;
      form.dataset.sending = "false";
    }
  });
})();
