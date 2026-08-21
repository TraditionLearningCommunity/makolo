const button = document.getElementById('discover-near-me');
const status = document.getElementById('discover-geolocation-status');
if (button) {
  button.addEventListener('click', () => {
    if (!navigator.geolocation) {
      if (status) status.textContent = 'Localisation indisponible. Recherchez un lieu manuellement.';
      return;
    }
    button.disabled = true;
    if (status) status.textContent = 'Localisation en cours…';
    navigator.geolocation.getCurrentPosition(
      (position) => {
        document.getElementById('discover-lat').value = position.coords.latitude.toFixed(6);
        document.getElementById('discover-lon').value = position.coords.longitude.toFixed(6);
        document.getElementById('discovery-search-form').requestSubmit();
      },
      () => {
        button.disabled = false;
        if (status) status.textContent = 'Localisation refusée. Vous pouvez saisir un lieu.';
      },
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 60000 },
    );
  });
}
