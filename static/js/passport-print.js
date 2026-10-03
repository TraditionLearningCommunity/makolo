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

  if (document.body?.dataset.passportAutoprint === "true") {
    window.print();
  }
});
