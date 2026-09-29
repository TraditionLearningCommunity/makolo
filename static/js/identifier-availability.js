(() => {
  const inputs = document.querySelectorAll('[data-identifier-check="true"]');
  for (const input of inputs) {
    const url = input.dataset.availabilityUrl;
    if (!url) continue;

    const status = document.createElement("p");
    status.className = "mt-2 text-xs";
    status.setAttribute("aria-live", "polite");
    input.insertAdjacentElement("afterend", status);

    let timer = null;
    let requestId = 0;

    const render = (text, state = "") => {
      status.textContent = text;
      status.dataset.state = state;
    };

    input.addEventListener("input", () => {
      const value = input.value.trim();
      window.clearTimeout(timer);
      requestId += 1;
      const current = requestId;

      if (value.length < 3) {
        render("");
        return;
      }

      render("Vérification…", "checking");
      timer = window.setTimeout(async () => {
        try {
          const response = await fetch(`${url}?value=${encodeURIComponent(value)}`, {
            credentials: "same-origin",
            headers: {"Accept": "application/json"},
          });
          if (!response.ok) throw new Error("availability");
          const payload = await response.json();
          if (current !== requestId) return;

          if (payload.available) {
            render(`@${payload.username} est disponible.`, "available");
          } else if (payload.reason === "invalid" && payload.errors?.length) {
            render(payload.errors[0], "invalid");
          } else {
            render("Cet identifiant est déjà utilisé.", "taken");
          }
        } catch (_error) {
          if (current === requestId) {
            render("La disponibilité sera vérifiée à l’envoi.", "unknown");
          }
        }
      }, 350);
    });
  }
})();
