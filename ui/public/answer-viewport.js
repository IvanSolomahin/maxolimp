// Keep the answer controls in the visible part of mobile webviews while typing.
(() => {
  const input = document.querySelector('#detail-user-answer, #answer-input');
  if (!input) return;

  const mobile = window.matchMedia('(max-width: 700px)');
  const viewport = window.visualViewport;

  function update() {
    const focused = document.activeElement === input && mobile.matches;
    document.body.classList.toggle('answer-input-focused', focused);

    const visibleBottom = viewport
      ? viewport.offsetTop + viewport.height
      : window.innerHeight;
    const inset = focused ? Math.max(0, window.innerHeight - visibleBottom) : 0;
    document.body.style.setProperty('--keyboard-inset', `${Math.ceil(inset)}px`);

    if (focused && inset > 100) {
      requestAnimationFrame(() => {
        const controls = input.closest('.detail-answer-row, .answer-row') || input;
        const overflow = controls.getBoundingClientRect().bottom - visibleBottom + 16;
        if (overflow > 0) window.scrollBy(0, overflow);
      });
    }
  }

  input.addEventListener('focus', update);
  input.addEventListener('blur', update);
  window.addEventListener('resize', update);
  viewport?.addEventListener('resize', update);
  viewport?.addEventListener('scroll', update);
  mobile.addEventListener('change', update);
})();
