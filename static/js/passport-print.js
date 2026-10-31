document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-passport-avatar]").forEach((avatar) => {
    avatar.addEventListener("error", () => {
      avatar.hidden = true;
      const fallback = avatar.nextElementSibling;
      if (fallback) {
        fallback.hidden = false;
      }
    });
  });


  document.querySelectorAll("[data-passport-share]").forEach((button) => {
    button.addEventListener("click", async () => {
      const url = button.getAttribute("data-public-url");
      if (!url) return;
      if (navigator.share) {
        try { await navigator.share({ title: "Passeport Makolo", url }); }
        catch (error) { if (error.name !== "AbortError") window.prompt("Lien public :", url); }
      } else {
        try { await navigator.clipboard.writeText(url); button.textContent = "Lien copié"; }
        catch (_) { window.prompt("Lien public :", url); }
      }
    });
  });
  document.querySelectorAll("[data-passport-copy]").forEach((button) => {
    button.addEventListener("click", async () => {
      const url = button.getAttribute("data-passport-copy");
      try { await navigator.clipboard.writeText(url); button.textContent = "Lien copié"; }
      catch (_) { window.prompt("Copiez ce lien public :", url); }
    });
  });

  if (document.body?.dataset.passportAutoprint === "true") {
    window.print();
  }
});
