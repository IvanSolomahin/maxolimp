const next = new URLSearchParams(location.search).get('next');
const destination = next && next.startsWith('/') && !next.startsWith('//') ? next : './olympiad-statistics.html';
window.maxUserReady.then(async user => {
  if (user) { location.replace(destination); return; }
  try {
    const response = await fetch('/api/auth/me');
    if (response.ok) location.replace(destination);
  } catch {}
});
