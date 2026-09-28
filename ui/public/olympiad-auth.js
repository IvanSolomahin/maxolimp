const next = new URLSearchParams(location.search).get('next');
const destination = next && next.startsWith('/') && !next.startsWith('//') ? next : './olympiad-statistics.html';
const errorBox = document.getElementById('auth-error');
const registerMode = new URLSearchParams(location.search).get('mode') === 'register';
const loginButton = document.getElementById('login-button');
const registerButton = document.getElementById('register-button');

if (registerMode) {
  document.title = 'Регистрация — Maxolimp';
  document.getElementById('auth-title').textContent = 'Создать аккаунт';
  document.getElementById('auth-description').textContent = 'Зарегистрируйтесь по email, чтобы сохранять решённые задачи и видеть свою статистику.';
  loginButton.hidden = true;
  registerButton.textContent = 'Зарегистрироваться';
  document.getElementById('auth-switch').innerHTML = 'Уже есть аккаунт? <a href="./olympiad-auth.html">Войти</a>';
}

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
      errorBox.textContent = action === 'register'
        ? response.status === 409 ? 'Этот email уже зарегистрирован. Войдите или укажите другой адрес.' : 'Не удалось создать аккаунт. Проверьте email и пароль.'
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
  submitAuth(registerMode ? 'register' : 'login');
});
registerButton.addEventListener('click', () => submitAuth('register'));
window.maxUserReady.then(async user => {
  if (user) { location.replace(destination); return; }
  try {
    const response = await fetch('/api/auth/me');
    if (response.ok) location.replace(destination);
  } catch {}
});
