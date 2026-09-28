const next = new URLSearchParams(location.search).get('next');
const destination = next && next.startsWith('/') && !next.startsWith('//') ? next : './olympiad-statistics.html';
const errorBox = document.getElementById('auth-error');

async function submitAuth(action) {
  errorBox.hidden = true;
  const email = document.getElementById('auth-email').value.trim();
  const password = document.getElementById('auth-password').value;
  if (!document.getElementById('auth-form').reportValidity()) return;
  try {
    const response = await fetch(`/api/auth/${action}`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({email, password}),
    });
    if (!response.ok) {
      errorBox.textContent = action === 'register' && response.status === 409
        ? 'Этот email уже зарегистрирован.'
        : 'Не удалось войти. Проверьте email и пароль.';
      errorBox.hidden = false;
      return;
    }
    location.replace(destination);
  } catch {
    errorBox.textContent = 'Нет соединения с сервером. Повторите попытку.';
    errorBox.hidden = false;
  }
}

document.getElementById('auth-form').addEventListener('submit', event => {
  event.preventDefault();
  submitAuth('login');
});
document.getElementById('register-button').addEventListener('click', () => submitAuth('register'));
window.maxUserReady.then(user => { if (user) location.replace(destination); });
