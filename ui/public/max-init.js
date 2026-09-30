(function () {
  const ENDPOINT = '/api/max/validate';
  const startParam = new URLSearchParams(location.search).get('WebAppStartParam')
    || window.WebApp?.initDataUnsafe?.start_param;
  const taskMatch = /^task_([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$/i.exec(startParam || '');
  if (taskMatch && /^\/(?:olympiad-home\.html|olympiad-task-search\.html)?$/.test(location.pathname)) {
    location.replace(`/tasks/${taskMatch[1]}${location.hash}`);
    return;
  }

  function getInitData() {
    return (window.WebApp && window.WebApp.initData) || '';
  }

  async function validate() {
    const initData = getInitData();
    if (!initData) return null;

    try {
      const existing = await fetch('/api/auth/me');
      if (existing.ok) {
        const account = await existing.json();
        const hinted = JSON.parse(new URLSearchParams(initData).get('user') || '{}');
        if (account.max_id === hinted.id) return { valid: true, user: account };
      }
    } catch {}

    try {
      const response = await fetch(ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ initData }),
      });
      if (!response.ok) return null;
      const data = await response.json();
      if (data.valid) return data;
    } catch (error) {
      console.warn('MAX initData validation failed:', error);
    }
    return null;
  }

  window.maxUserReady = validate();
})();
