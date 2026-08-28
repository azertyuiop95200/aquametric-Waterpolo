(() => {
  const grid = document.querySelector('[data-registry-grid]');
  if (!grid) return;
  const cards = [...grid.querySelectorAll('[data-reg-card]')];
  const buttons = [...document.querySelectorAll('[data-reg-filter]')];
  const count = document.querySelector('[data-reg-count]');
  const apply = (filter) => {
    let visible = 0;
    cards.forEach(card => {
      const show = filter === 'all' || (filter === 'priority' && card.dataset.priority === '1') || (filter === 'match' && card.dataset.match === '1');
      card.hidden = !show;
      if (show) visible += 1;
    });
    buttons.forEach(btn => btn.classList.toggle('active', btn.dataset.regFilter === filter));
    if (count) count.textContent = `${visible} dossier${visible > 1 ? 's' : ''}`;
  };
  buttons.forEach(btn => btn.addEventListener('click', () => apply(btn.dataset.regFilter)));
})();
