// Browser users can register before opening progress features. MAX users are
// authenticated by max-init.js and do not need this prompt.
window.maxUserReady?.then(user => {
  if (user) return;
  fetch('/api/auth/me').then(response => {
    if (response.status === 401) document.getElementById('browser-signup').hidden = false;
  }).catch(() => { document.getElementById('browser-signup').hidden = false; });
});
