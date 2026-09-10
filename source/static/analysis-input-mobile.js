(() => {
  const $ = id => document.getElementById(id);
  if (!$('analysisForm')) return;
  const desktopButton = $('desktopAnalysisMode'), phoneButton = $('phoneAnalysisMode');
  const desktopUrl = $('desktopVideoUrl'), phoneUrl = $('phoneVideoUrl'), phoneFile = $('phoneVideoFile');
  let mode = 'desktop';
  function syncSource() {
    const desktop = mode === 'desktop', link = !desktop && $('phoneSource').value === 'link';
    desktopUrl.disabled = !desktop; desktopUrl.required = desktop;
    phoneUrl.disabled = !link; phoneUrl.required = link;
    phoneFile.disabled = desktop || link; phoneFile.required = !desktop && !link;
    $('phoneLinkPanel').hidden = !link; $('phoneFilePanel').hidden = desktop || link;
    $('desktopAnalyzeSubmit').disabled = !desktop; $('phoneLinkSubmit').disabled = !link;
    $('phoneAnalyzeSubmit').disabled = desktop || link;
    $('scopeMode').disabled = !desktop;
    document.querySelectorAll('#scopeManual input').forEach(input => { input.disabled = !desktop; });
  }
  function selectMode(value) {
    mode = value; const desktop = mode === 'desktop';
    $('analysisInputDevice').value = mode;
    desktopButton.classList.toggle('active', desktop); phoneButton.classList.toggle('active', !desktop);
    desktopButton.setAttribute('aria-pressed', String(desktop)); phoneButton.setAttribute('aria-pressed', String(!desktop));
    $('desktopModePanel').classList.toggle('active', desktop); $('phoneModePanel').classList.toggle('active', !desktop);
    syncSource();
  }
  desktopButton.addEventListener('click', () => selectMode('desktop'));
  phoneButton.addEventListener('click', () => selectMode('phone'));
  $('phoneSource').addEventListener('change', syncSource);
  $('scopeMode').addEventListener('change', () => { $('scopeManual').hidden = !['multiple', 'manual'].includes($('scopeMode').value); });
  const mobileLike = window.matchMedia('(max-width: 700px)').matches || /Android|iPhone|iPad|iPod/i.test(navigator.userAgent || '');
  selectMode(mobileLike ? 'phone' : 'desktop');
  $('analysisForm').addEventListener('submit', event => {
    // Enter in a URL field must follow the active source, not the outer upload action.
    if (!event.submitter) {
      event.preventDefault();
      $('analysisForm').requestSubmit($(mode === 'desktop' ? 'desktopAnalyzeSubmit' : $('phoneSource').value === 'link' ? 'phoneLinkSubmit' : 'phoneAnalyzeSubmit'));
    }
  });
})();
