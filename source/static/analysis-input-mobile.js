(() => {
  const $ = id => document.getElementById(id);
  const form = $('analysisForm');
  if (!form) return;
  const desktopButton = $('desktopAnalysisMode'), phoneButton = $('phoneAnalysisMode');
  const desktopUrl = $('desktopVideoUrl'), desktopFile = $('desktopVideoFile');
  const phoneUrl = $('phoneVideoUrl'), phoneFile = $('phoneVideoFile');
  let mode = 'desktop';
  function syncSource() {
    const desktop = mode === 'desktop';
    const desktopLink = desktop && $('desktopSource').value === 'link';
    const desktopUpload = desktop && !desktopLink;
    const phoneLink = !desktop && $('phoneSource').value === 'link';
    const phoneUpload = !desktop && !phoneLink;

    desktopUrl.disabled = !desktopLink;
    desktopUrl.required = desktopLink;
    desktopFile.disabled = !desktopUpload;
    desktopFile.required = desktopUpload;
    phoneUrl.disabled = !phoneLink;
    phoneUrl.required = phoneLink;
    phoneFile.disabled = !phoneUpload;
    phoneFile.required = phoneUpload;

    $('desktopLinkPanel').hidden = !desktopLink;
    $('desktopFilePanel').hidden = !desktopUpload;
    $('phoneLinkPanel').hidden = !phoneLink;
    $('phoneFilePanel').hidden = !phoneUpload;

    $('desktopAnalyzeSubmit').disabled = !desktopLink;
    $('desktopAnalyzeSubmit').hidden = !desktopLink;
    $('desktopFileAnalyzeSubmit').disabled = !desktopUpload;
    $('desktopFileAnalyzeSubmit').hidden = !desktopUpload;
    $('phoneLinkSubmit').disabled = !phoneLink;
    $('phoneAnalyzeSubmit').disabled = !phoneUpload;
    $('scopeMode').disabled = !desktopLink;
    $('youtubeDurationMinutes').disabled = desktopUpload || phoneUpload;
    document.querySelectorAll('#scopeManual input').forEach(input => {
      input.disabled = !desktopLink;
    });
  }
  function selectMode(value) {
    mode = value;
    const desktop = mode === 'desktop';
    $('analysisInputDevice').value = mode;
    desktopButton.classList.toggle('active', desktop);
    phoneButton.classList.toggle('active', !desktop);
    desktopButton.setAttribute('aria-pressed', String(desktop));
    phoneButton.setAttribute('aria-pressed', String(!desktop));
    $('desktopModePanel').classList.toggle('active', desktop);
    $('phoneModePanel').classList.toggle('active', !desktop);
    syncSource();
  }
  desktopButton.addEventListener('click', () => selectMode('desktop'));
  phoneButton.addEventListener('click', () => selectMode('phone'));
  $('desktopSource').addEventListener('change', syncSource);
  $('phoneSource').addEventListener('change', syncSource);
  $('scopeMode').addEventListener('change', () => {
    $('scopeManual').hidden = !['multiple', 'manual'].includes($('scopeMode').value);
  });
  const mobileLike = window.matchMedia('(max-width: 700px)').matches ||
    /Android|iPhone|iPad|iPod/i.test(navigator.userAgent || '');
  selectMode(mobileLike ? 'phone' : 'desktop');
  const quickOpen = kind => {
    const isPhone = mobileLike;
    selectMode(isPhone ? 'phone' : 'desktop');
    const selector = $(isPhone ? 'phoneSource' : 'desktopSource');
    selector.value = kind === 'youtube' ? 'link' : 'file';
    selector.dispatchEvent(new Event('change', {bubbles:true}));
    const field = $(isPhone
      ? (kind === 'youtube' ? 'phoneVideoUrl' : 'phoneVideoFile')
      : (kind === 'youtube' ? 'desktopVideoUrl' : 'desktopVideoFile'));
    field.scrollIntoView({behavior:'smooth',block:'center'});
    field.focus({preventScroll:true});
    // Do not submit or upload until the user has selected an actual source.
    // The required team fields and format validation remain enforced.
  };
  $('quickYoutubeAnalysis')?.addEventListener('click', () => quickOpen('youtube'));
  $('quickFileAnalysis')?.addEventListener('click', () => quickOpen('file'));

  form.addEventListener('submit', event => {
    // Enter from any text field must submit the currently selected video source.
    if (!event.submitter) {
      event.preventDefault();
      const submitter = mode === 'desktop'
        ? ($('desktopSource').value === 'link' ? $('desktopAnalyzeSubmit') : $('desktopFileAnalyzeSubmit'))
        : ($('phoneSource').value === 'link' ? $('phoneLinkSubmit') : $('phoneAnalyzeSubmit'));
      form.requestSubmit(submitter);
    }
  });
})();
