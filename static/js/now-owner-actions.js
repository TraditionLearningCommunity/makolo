/* Focused Now actions use the exact existing owner API, never generic POST. */
(() => {
  "use strict";
  const root = document.querySelector('[data-mk-surface="now"]');
  if (!root) return;

  const uuidPattern =
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  const permitted = {
    recognition_redemption: {
      prefix: "/api/v1/recognition/redemptions/",
      capabilities: ["accept", "decline"],
    },
    waitlist: {
      prefix: "/api/v1/tickets/waitlist/",
      capabilities: ["accept", "leave"],
    },
    ticket_transfer: {
      prefix: "/api/v1/tickets/transfers/",
      capabilities: ["accept", "decline"],
    },
  };

  root.addEventListener("submit", async (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) ||
        !form.matches("[data-now-direct]")) return;
    event.preventDefault();
    const ownerId = form.dataset.ownerId || "";
    const ownerKind = form.dataset.ownerKind || "";
    const capability = form.dataset.capability || "";
    const rule = permitted[ownerKind];
    if (!rule || !rule.capabilities.includes(capability) ||
        !uuidPattern.test(ownerId) || form.dataset.sending === "true") return;

    const target = new URL(form.action, window.location.origin);
    if (target.origin !== window.location.origin ||
        target.search || target.hash ||
        target.pathname.toLowerCase() !==
          (rule.prefix + ownerId + "/" + capability + "/").toLowerCase()) return;

    const button = form.querySelector('button[type="submit"]');
    const feedback = form.querySelector("output");
    const csrf = form.querySelector('input[name="csrfmiddlewaretoken"]');
    if (!button || !feedback || !csrf) return;
    if (!window.confirm("Confirmer la décision « " +
        button.textContent.trim() + " » ?")) return;

    form.dataset.sending = "true";
    const neighbors = form.closest(".mk-now-business-actions");
    const buttons = neighbors
      ? Array.from(neighbors.querySelectorAll('button[type="submit"]'))
      : [button];
    buttons.forEach((item) => { item.disabled = true; });
    feedback.textContent = "Envoi de votre décision au propriétaire…";
    try {
      const response = await fetch(target.toString(), {
        method: "POST",
        credentials: "same-origin",
        cache: "no-store",
        redirect: "error",
        headers: {
          Accept: "application/json",
          "X-CSRFToken": csrf.value,
        },
      });
      const data = await response.json();
      const confirmed = response.ok && (
        ownerKind === "waitlist" && capability === "accept"
          ? uuidPattern.test(String(data.id || "")) &&
              typeof data.status === "string"
          : String(data.id || "").toLowerCase() === ownerId.toLowerCase()
      );
      if (!confirmed) throw new Error("Owner confirmation missing");
      feedback.textContent = "Décision confirmée par le propriétaire.";
      window.location.reload();
    } catch (_) {
      feedback.textContent =
        "Cette décision n’a pas été confirmée. Vérifiez son état auprès du propriétaire.";
      buttons.forEach((item) => { item.disabled = false; });
      form.dataset.sending = "false";
    }
  });
})();
