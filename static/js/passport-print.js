document.addEventListener("DOMContentLoaded", () => {
  if (document.body?.dataset.passportAutoprint === "true") {
    window.print();
  }
});
