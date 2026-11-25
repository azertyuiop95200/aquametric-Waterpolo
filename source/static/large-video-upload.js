/* Direct-to-R2/S3 resumable multipart upload.
   No gigabyte request body ever goes through the Render/FastAPI web service.
   Each part is at most 16 MiB; server verifies all S3 parts before linking.
*/
(() => {
  const $ = id => document.getElementById(id);
  const fileInput = $('largeUploadVideo');
  if (!fileInput) return;
  const start = $('largeUploadStart'), cancel = $('largeUploadCancel');
  const status = $('largeUploadStatus'), progress = $('largeUploadProgress');
  const limit = $('largeUploadLimit'), form = $('segmentUploadForm') || $('analysisForm');
  if (!form) return;
  const targetMatchId = form.dataset.targetMatchId ? Number(form.dataset.targetMatchId) : null;
  let config = null, busy = false, abortController = null, currentId = '', currentKey = '';

  function say(text) { status.textContent = text; }
  function sizeText(bytes) { return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' Go'; }
  function cacheKey(file) {
    // Match the *same* local file on resume; the server independently enforces
    // ownership, filename, byte count and every uploaded part.
    return 'aquametric-large-upload:' + (targetMatchId || 'new') + ':' + file.name + ':' + file.size + ':' + file.lastModified;
  }
  async function jsonApi(path, opts) {
    const response = await fetch(path, {
      credentials: 'same-origin',
      ...opts,
      headers: {'Content-Type':'application/json', ...(opts?.headers || {})}
    });
    let payload = {};
    try {payload = await response.json();} catch(e) {}
    if (!response.ok) throw new Error(typeof payload.detail === 'string' ? payload.detail :
      'Erreur HTTP ' + response.status);
    return payload;
  }
  function nameValue(name) {
    return form.querySelector('[name="' + name + '"]')?.value?.trim() || '';
  }
  function controls(running) {
    busy = running;
    start.disabled = running || !config?.enabled || !fileInput.files?.length;
    fileInput.disabled = running;
    cancel.hidden = !running;
  }
  function onFileChanged() {
    const file = fileInput.files?.[0];
    controls(false);
    if (!file) { say('Sélectionne un fichier vidéo.'); return; }
    if (!config?.enabled) { say(config?.reason || 'Stockage cloud indisponible.'); return; }
    if (file.size > config.max_bytes) {
      say('Fichier trop volumineux : ' + sizeText(file.size) + ' dépasse la limite ' + config.max_gb + ' Go.');
      start.disabled = true; return;
    }
    const persisted = localStorage.getItem(cacheKey(file));
    start.textContent = persisted ? 'Reprendre le transfert interrompu' : 'Envoyer ' + sizeText(file.size);
    say(persisted
      ? 'Transfert précédent détecté : resélectionne ce fichier et clique pour reprendre.'
      : 'Prêt pour un transfert direct et sécurisé en ' + Math.ceil(file.size / config.part_bytes) + ' morceaux.');
  }
  async function sendOne(file, sessionId, partIndex, partBytes, total, completed, controller) {
    const first = (partIndex - 1) * partBytes;
    const last = Math.min(file.size, first + partBytes);
    for (let retry = 0; retry < 4; retry++) {
      if (controller.signal.aborted) throw new Error('Envoi interrompu.');
      try {
        const signed = await jsonApi('/api/large-upload/' + encodeURIComponent(sessionId) + '/sign',
          {method:'POST', body:JSON.stringify({number:partIndex}),signal:controller.signal});
        const response = await fetch(signed.url, {
          method:'PUT', body:file.slice(first,last),signal:controller.signal,
        });
        if (!response.ok) throw new Error('Morceau ' + partIndex + ' refusé par le stockage : HTTP ' + response.status);
        completed.add(partIndex);
        progress.value = 100 * completed.size / total;
        say('Envoi en cours : ' + completed.size + '/' + total +
          ' morceaux (' + Math.floor(progress.value) + '%). Tu peux reprendre ce transfert si la connexion coupe.');
        return;
      } catch (error) {
        if (controller.signal.aborted) throw error;
        if (retry === 3) throw error;
        await new Promise(resolve => setTimeout(resolve, (retry + 1) * 900));
      }
    }
  }
  async function begin() {
    const file = fileInput.files?.[0];
    if (!file || busy || !config?.enabled) return;
    if (!nameValue('team_name') || !nameValue('opponent')) {
      say('Indique le nom des deux équipes avant d’importer le fichier.'); return;
    }
    if (file.size <= 0 || file.size > config.max_bytes) {
      say('Le fichier doit être non vide et ne pas dépasser ' + config.max_gb + ' Go.'); return;
    }
    const key = cacheKey(file);
    currentKey = key;
    const controller = new AbortController();
    abortController = controller;
    controls(true);
    try {
      let session = localStorage.getItem(key);
      let state = null;
      if (session) {
        state = await jsonApi('/api/large-upload/' + encodeURIComponent(session) + '/status',{signal:controller.signal});
        if (state.status === 'complete') {
          localStorage.removeItem(key);
          window.location.assign(state.match_url);
          return;
        }
      } else {
        const created = await jsonApi('/api/large-upload/start', {
          method:'POST', signal:controller.signal,
          body:JSON.stringify({
            filename:file.name, size_bytes:file.size,
            team_name:nameValue('team_name'),opponent:nameValue('opponent'),
            category:nameValue('category') || 'Women',
            competition:nameValue('competition'),match_date:nameValue('match_date'),
            match_id:targetMatchId, period:Number(nameValue('period') || 1),
            segment_label:nameValue('segment_label')
          }),
        });
        session = created.upload_id;
        localStorage.setItem(key, session);
        state = await jsonApi('/api/large-upload/' + encodeURIComponent(session) + '/status',
          {signal:controller.signal});
      }
      currentId = session;
      const partBytes = state.part_bytes || config.part_bytes;
      const partCount = Math.ceil(file.size / partBytes);
      const completed = new Set(state.completed_parts || []);
      progress.value = 100 * completed.size / partCount;
      const todo = [];
      for (let number=1; number<=partCount; number++) {
        if (!completed.has(number)) todo.push(number);
      }
      say('Envoi ' + sizeText(file.size) + ' : ' + completed.size +
        '/' + partCount + ' morceaux déjà enregistrés.');
      let next=0;
      const worker = async () => {
        while (next < todo.length) {
          if (controller.signal.aborted) return;
          const number = todo[next++];
          await sendOne(file,session,number,partBytes,partCount,completed,controller);
        }
      };
      // At most three 16 MiB blobs concurrently. Browser memory stays bounded.
      await Promise.all(Array.from({length:Math.min(3,todo.length)},worker));
      if (controller.signal.aborted) return;
      say('Tous les morceaux sont reçus. Vérification et assemblage du fichier…');
      const done = await jsonApi('/api/large-upload/' + encodeURIComponent(session) + '/complete',{
        method:'POST', signal:controller.signal
      });
      progress.value=100;
      localStorage.removeItem(key);
      currentId='';
      say('Vidéo enregistrée (' + sizeText(file.size) + '). Ouverture du dossier…');
      window.location.assign(done.match_url);
    } catch (err) {
      say('Transfert interrompu : ' + (err?.message || err) +
        '. Resélectionne le même fichier pour le reprendre sans recommencer.');
      start.textContent='Reprendre le transfert';
    } finally {
      controls(false);
    }
  }
  start.addEventListener('click',begin);
  fileInput.addEventListener('change',onFileChanged);
  cancel.addEventListener('click', async () => {
    // Cancel is destructive, unlike a transient network failure: abort the
    // remote multipart job and release quota if an upload ID is known.
    if (!busy) return;
    const id=currentId, key=currentKey;
    abortController?.abort();
    if (id) {
      try {
        await jsonApi('/api/large-upload/' + encodeURIComponent(id),{method:'DELETE'});
        localStorage.removeItem(key);
        say('Transfert annulé. Le stockage cloud a été libéré.');
      } catch(err) {say('Interruption locale. Tu peux reprendre ou demander l’annulation : ' + err.message);}
    } else say('Envoi interrompu avant initialisation.');
    currentId='';
    controls(false);
  });
  jsonApi('/api/large-upload/capabilities')
    .then(result => {
      config = result;
      limit.textContent=String(config.max_gb || 5);
      if (!config.enabled) {
        say('Import de plusieurs Go non activé : ' + config.reason +
          ' Le formulaire classique reste disponible pour les petites vidéos.');
      } else {
        say('Stockage cloud sécurisé prêt. Sélectionne ton MP4 ou MOV.');
      }
      onFileChanged();
    })
    .catch(err => {say('Impossible de vérifier le stockage des gros fichiers : '+err.message);start.disabled=true;});
})();
