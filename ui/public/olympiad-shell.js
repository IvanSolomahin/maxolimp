const tabs = [
  { id: 'home', label: 'Главная', href: './olympiad-home.html', icon: '<path d="m3 11 9-8 9 8M5 10v10h14V10"/>' },
  { id: 'tasks', label: 'Задачи', href: './olympiad-task-search.html', icon: '<path d="M9 11l3 3 8-8M20 12v6a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h9"/>' },
  { id: 'communities', label: 'Сообщества', href: './olympiad-community.html', icon: '<circle cx="8" cy="8" r="3"/><circle cx="17" cy="9" r="2.6"/><path d="M2.5 19c.6-3.2 2.9-5 5.5-5s4.9 1.8 5.5 5M14.5 14.3c2.1.2 3.9 1.8 4.4 4.7"/>' },
];

const headerStyle = `
  *, *::before, *::after { box-sizing:border-box; }
  :host { display:block; position:sticky; top:0; z-index:20; background:color-mix(in oklab,var(--bg,#fff) 94%,transparent); border-bottom:1px solid var(--border-soft,#eee); backdrop-filter:blur(16px); color:var(--fg,#111); }
  header { width:min(100%,1160px); min-height:var(--app-header-height,68px); margin:auto; padding:10px 24px; display:flex; align-items:center; justify-content:space-between; gap:32px; }
  .brand { color:inherit; font:600 20px/1.2 var(--font-display,Inter,system-ui,sans-serif); letter-spacing:-.04em; text-decoration:none; white-space:nowrap; }
  .brand span { color:#95bc42; }
  .page-title { margin-right:auto; color:var(--muted,#707070); font:600 13px/1.3 var(--font-body,Inter,system-ui,sans-serif); }
  nav { display:flex; align-items:center; gap:28px; }
  nav a { color:var(--muted,#707070); font:600 13px/1.3 var(--font-body,Inter,system-ui,sans-serif); text-decoration:none; white-space:nowrap; }
  nav a:hover,nav a[aria-current="page"] { color:var(--fg,#111); }
  nav a[aria-current="page"] { text-decoration:underline; text-decoration-color:#d7fa6c; text-decoration-thickness:3px; text-underline-offset:8px; }
  @media(max-width:700px) { header { padding:8px 20px; gap:16px; } .brand { font-size:18px; } .page-title { margin-right:0; text-align:right; font-size:12px; } header nav { display:none; } }
`;

class OlympiadHeader extends HTMLElement {
  connectedCallback() {
    const active = this.getAttribute('active') || 'home';
    const title = this.getAttribute('title') || 'maxolimp';
    this.attachShadow({ mode: 'open' }).innerHTML = `<style>${headerStyle}</style><header><a class="brand" href="./olympiad-home.html">maxolimp<span>.</span></a>${title === 'maxolimp' ? '' : `<span class="page-title">${title}</span>`}<nav aria-label="Основные разделы">${tabs.map(t => `<a href="${t.href}" ${t.id === active ? 'aria-current="page"' : ''}>${t.label}</a>`).join('')}</nav></header>`;
  }
}

class OlympiadNav extends HTMLElement {
  connectedCallback() {
    const active = this.getAttribute('active') || 'home';
    this.attachShadow({ mode: 'open' }).innerHTML = `<style>
      *, *::before, *::after { box-sizing:border-box; }
      :host { display:block; position:fixed; inset:auto 0 0; z-index:20; padding-bottom:env(safe-area-inset-bottom); background:color-mix(in oklab,var(--bg,#fff) 96%,transparent); border-top:1px solid var(--border-soft,#eee); backdrop-filter:blur(18px); color:var(--fg,#111); }
      .footer { width:min(100%,760px); margin:auto; }
      .brand { display:block; width:max-content; margin:7px auto 0; color:var(--fg,#111); font:700 13px/1.2 var(--font-display,Inter,system-ui,sans-serif); letter-spacing:-.04em; text-decoration:none; }
      .brand span { color:#95bc42; }
      nav { min-height:calc(var(--app-nav-height,70px) - 24px); padding:3px 16px 6px; display:flex; align-items:center; justify-content:center; gap:clamp(20px,5vw,56px); }
      a { display:flex; align-items:center; gap:8px; padding:8px; color:var(--muted,#707070); font:600 13px/1.3 var(--font-body,Inter,system-ui,sans-serif); text-decoration:none; }
      a[aria-current="page"] { color:var(--fg,#111); }
      svg { width:20px; height:20px; flex:none; fill:none; stroke:currentColor; stroke-width:1.7; stroke-linecap:round; stroke-linejoin:round; }
      @media(max-width:700px) { nav { justify-content:space-around; gap:0; padding:2px 12px 4px; } a { flex-direction:column; gap:2px; font-size:10px; } svg { width:22px; height:22px; } }
    </style><div class="footer"><a class="brand" href="./olympiad-home.html" aria-label="maxolimp — главная">maxolimp<span>.</span></a><nav aria-label="Разделы">${tabs.map(t => `<a href="${t.href}" ${t.id === active ? 'aria-current="page"' : ''}><svg viewBox="0 0 24 24" aria-hidden="true">${t.icon}</svg>${t.label}</a>`).join('')}</nav></div>`;
  }
}

customElements.define('olympiad-header', OlympiadHeader);
customElements.define('olympiad-nav', OlympiadNav);
