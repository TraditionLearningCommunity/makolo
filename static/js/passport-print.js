document.addEventListener("click", (event) => {
  const trigger = event.target.closest("[data-passport-print]");
  if (!trigger) return;
  window.print();
});
