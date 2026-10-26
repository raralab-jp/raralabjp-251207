(() => {
  const controls = document.querySelector('.gallery-filter');
  const select = document.querySelector('#gallery-species');
  const grid = document.querySelector('main.gallery-index > .rl-gallery');
  const all = document.querySelector('#gallery-all-items');
  if (!controls || !select || !grid || !all) return;
  const original = [...grid.childNodes].map(node => node.cloneNode(true));
  const pager = document.querySelector('.gallery-pager');
  const status = controls.querySelector('[role="status"]');
  const total = all.content.querySelectorAll('.rl-item').length;
  const page = Number(location.pathname.match(/^\/gallery\/page-([1-9]\d*)(?:\.html)?\/?$/)?.[1] || 1);
  function apply() {
    const key = select.value;
    if (key) {
      const cards = [...all.content.querySelectorAll('.rl-item')].filter(card => card.dataset.species === key);
      grid.replaceChildren(...cards.map(card => card.cloneNode(true)));
      if (pager) pager.hidden = true;
      status.textContent = `${cards.length}点 / 全${total}点から絞り込み`;
    } else {
      grid.replaceChildren(...original.map(node => node.cloneNode(true)));
      if (pager) pager.hidden = false;
      status.textContent = `全${total}点 / ${page}ページ目・${grid.querySelectorAll('.rl-item').length}点を表示`;
    }
    const url = new URL(location.href);
    if (key) url.searchParams.set('species', key); else url.searchParams.delete('species');
    history.replaceState(null, '', url);
  }
  function restore() {
    const key = new URLSearchParams(location.search).get('species') || '';
    select.value = [...select.options].some(o => o.value === key) ? key : '';
    apply();
  }
  select.addEventListener('change', apply);
  window.addEventListener('popstate', restore);
  controls.hidden = false;
  restore();
})();
