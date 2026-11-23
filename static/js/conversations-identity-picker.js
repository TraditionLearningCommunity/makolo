(() => {
  "use strict";
  const form = document.querySelector("[data-participant-invite-form]");
  if (!form) return;
  const input = form.querySelector("[data-identity-input]");
  const kind = form.querySelector("[data-identity-kind]");
  const box = form.querySelector("[data-identity-suggestions]");
  const status = form.querySelector("[data-identity-status]");
  if (!input || !kind || !box || !form.dataset.searchUrl) return;
  let latest = 0;
  let pending = null;

  function reset() { box.replaceChildren(); status.textContent = ""; }

  async function search() {
    const term = input.value.trim();
    const generation = ++latest;
    if (term.length < 2 || term.length > 80) { reset(); return; }
    status.textContent = "Recherche d'identifiants…";
    try {
      const url = new URL(form.dataset.searchUrl, window.location.origin);
      if (url.origin !== window.location.origin) throw Error("Adresse invalide.");
      url.searchParams.set("q", term);
      const response = await fetch(url.toString(), {
        credentials: "same-origin", cache: "no-store",
        headers: { "Accept": "application/json" },
      });
      if (!response.ok) throw Error("Suggestions indisponibles.");
      const payload = await response.json();
      if (generation !== latest) return;
      box.replaceChildren();
      const rows = Array.isArray(payload.results) ? payload.results : [];
      const selected = rows.filter((row) =>
        row.kind === kind.value && typeof row.identifier === "string");
      for (const row of selected) {
        const button = document.createElement("button");
        button.type = "button";
        button.setAttribute("role", "option");
        button.className = "flex w-full flex-col rounded-xl border p-3 text-left";
        button.style.borderColor = "var(--mk-border)";
        const name = document.createElement("span");
        name.className = "font-semibold";
        name.textContent = row.label || "Makolo";
        const identifier = document.createElement("span");
        identifier.className = "text-xs";
        identifier.style.color = "var(--mk-muted)";
        identifier.textContent = row.description ||
          ((row.kind === "profile" ? "@" : "") + row.identifier);
        button.append(name, identifier);
        button.addEventListener("click", () => {
          input.value = row.identifier;
          kind.value = row.kind;
          reset();
          input.focus();
          status.textContent = "Identifiant sélectionné : " + row.identifier +
            ". L'invitation sera envoyée après confirmation.";
        });
        box.append(button);
      }
      status.textContent = selected.length
        ? "Sélectionnez un identifiant. Le nom n'est qu'une indication."
        : "Aucune suggestion publique. Vous pouvez saisir un identifiant exact connu.";
    } catch (error) {
      if (generation === latest) {
        box.replaceChildren();
        status.textContent = "Suggestions indisponibles. Utilisez l'identifiant exact.";
      }
    }
  }

  input.addEventListener("input", () => {
    clearTimeout(pending);
    pending = setTimeout(search, 240);
  });
  kind.addEventListener("change", () => {
    clearTimeout(pending);
    search();
  });
})();
