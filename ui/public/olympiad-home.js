// Explain how to save progress when the page is opened outside MAX.
window.maxUserReady?.then(user => {
  if (user) return;
  fetch('/api/auth/me').then(response => {
    if (response.status === 401) document.getElementById('browser-signup').hidden = false;
  }).catch(() => { document.getElementById('browser-signup').hidden = false; });
});
