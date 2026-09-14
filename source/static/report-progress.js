(() => {
  const panel = document.getElementById('captureReportProgress');
  if (!panel) return;
  const label = panel.querySelector('[data-progress-label]');
  const initialClips = Number(panel.dataset.clips || 0);
  const initialEnrichment = panel.dataset.enrichment;
  const deadline = Date.now() + 10 * 60 * 1000;
  let stopped = false;
  async function refresh() {
    if (stopped) return;
    if (Date.now() > deadline) {
      label.textContent = 'Le traitement ne répond plus. Recharge la page pour consulter les données déjà enregistrées.';
      return;
    }
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
      const response = await fetch(panel.dataset.url, {cache: 'no-store', signal: controller.signal});
      if ([401, 404].includes(response.status)) {
        label.textContent = 'Ce dossier n’est plus accessible avec ta session actuelle. Reconnecte-toi et ouvre ta bibliothèque.';
        stopped = true;
        return;
      }
      if (!response.ok) throw new Error('HTTP ' + response.status);
      const state = await response.json();
      label.textContent = `${state.media_clips} extrait(s) prêt(s)${state.media_targets ? ' sur ' + state.media_targets : ''}. ${state.enrichment_status === 'complete' ? 'Lectures du score consolidées.' : 'Vérification des lectures en cours.'}`;
      const changed = !state.active || state.enrichment_status !== initialEnrichment || (!initialClips && state.media_clips > 0);
      const playing = [...document.querySelectorAll('video')].some(video => !video.paused && !video.ended);
      if (changed && !playing) { location.reload(); return; }
    } catch (_) {
      label.textContent = 'Connexion momentanément interrompue. Nouvelle vérification dans quelques secondes…';
    } finally {
      clearTimeout(timeout);
    }
    setTimeout(refresh, 5000);
  }
  setTimeout(refresh, 2000);
})();
