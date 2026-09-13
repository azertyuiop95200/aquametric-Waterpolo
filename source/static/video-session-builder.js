(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  if (!$('session-builder')) return;
  let draft = {title: '', objective: '', items: [], revision: 1}, dirty = false, index = 0, busy = false;
  const status = text => { $('session-status').textContent = text; };
  const changed = () => { dirty = true; status('Modifications non enregistrées.'); };
  async function api(path = '', options = {}) {
    const response = await fetch('/api/video-sessions' + path, {credentials: 'same-origin', ...options});
    if (!response.ok) {
      let data; try { data = await response.json(); } catch (_) { /* response may be HTML */ }
      throw new Error(typeof data?.detail === 'string' ? data.detail : `Opération impossible (${response.status}).`);
    }
    return response.status === 204 ? null : response.json();
  }
  const guard = fn => async event => {
    event?.preventDefault();
    if (busy) return;
    busy = true; $('session-builder').inert = true;
    try { await fn(event); } catch (error) { status(error.message); } finally { busy = false; $('session-builder').inert = false; }
  };
  function button(label, action) {
    const b = document.createElement('button'); b.type = 'button'; b.className = 'btn'; b.textContent = label;
    b.addEventListener('click', action); return b;
  }
  function render() {
    $('session-title').value = draft.title; $('session-objective').value = draft.objective;
    $('session-items').replaceChildren();
    draft.items.forEach((item, i) => {
      const li = document.createElement('li'); li.style.marginBottom = '16px';
      const title = document.createElement('p'); title.textContent = `${item.title} · ${item.start}–${item.end} s`;
      const note = document.createElement('textarea'); note.value = item.note || ''; note.maxLength = 4000;
      note.placeholder = 'Observation, question au groupe, correction à transférer dans l’eau';
      note.setAttribute('aria-label', `Consignes : ${item.title}`);
      note.addEventListener('input', () => { item.note = note.value; changed(); });
      const up = button('Monter', () => { [draft.items[i-1], draft.items[i]] = [draft.items[i], draft.items[i-1]]; changed(); render(); });
      const down = button('Descendre', () => { [draft.items[i+1], draft.items[i]] = [draft.items[i], draft.items[i+1]]; changed(); render(); });
      up.disabled = i === 0; down.disabled = i === draft.items.length-1;
      li.append(title, note, up, down, button('Retirer', () => { draft.items.splice(i, 1); changed(); render(); }));
      $('session-items').append(li);
    });
    $('session-delete').hidden = !draft.id; $('session-export').hidden = !draft.id;
    if (draft.id) $('session-export').href = `/api/video-sessions/${draft.id}/export`;
  }
  async function list() {
    const rows = await api(); $('session-list').replaceChildren(new Option('Nouvelle séance', ''));
    rows.forEach(row => $('session-list').add(new Option(`${row.title} · ${row.count} extraits`, row.id)));
    $('session-list').value = draft.id || '';
  }
  async function save() {
    if (!$('session-form').reportValidity()) throw new Error('Renseigne le titre de la séance.');
    const result = await api(draft.id ? `/${draft.id}` : '', {
      method: draft.id ? 'PUT' : 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(draft)
    });
    draft = result; dirty = false; render(); await list(); status('Séance enregistrée.');
  }
  function closePresentation() { $('presentation-media').replaceChildren(); $('session-presentation').hidden = true; }
  function present() {
    const item = draft.items[index]; if (!item) return;
    $('session-presentation').hidden = false;
    $('presentation-title').textContent = `${index + 1}/${draft.items.length} · ${item.title}`;
    $('presentation-note').textContent = item.note || draft.objective;
    const media = $('presentation-media'); media.replaceChildren();
    if (item.video) {
      const video = document.createElement('video'); video.controls = true; video.playsInline = true;
      video.src = `${item.video}#t=${item.start},${item.end}`;
      video.addEventListener('loadedmetadata', () => { video.currentTime = item.start; });
      video.addEventListener('timeupdate', () => { if (video.currentTime >= item.end) video.pause(); });
      video.addEventListener('play', () => { if (video.currentTime >= item.end || video.currentTime < item.start) video.currentTime = item.start; });
      video.addEventListener('error', () => status('Vidéo indisponible. Vérifie la source du match.'));
      media.append(video);
    } else if (item.embed) {
      const frame = document.createElement('iframe'); const url = new URL(item.embed);
      url.searchParams.set('start', Math.floor(item.start)); url.searchParams.set('end', Math.ceil(item.end));
      frame.src = url.toString(); frame.title = item.title; frame.allowFullscreen = true; media.append(frame);
    } else { media.textContent = 'Source indisponible : rattache une vidéo au match pour lire ce passage.'; }
    $('presentation-prev').disabled = index === 0; $('presentation-next').disabled = index === draft.items.length - 1;
  }
  function add(item) {
    if (draft.items.length >= 100) throw new Error('Maximum 100 extraits par séance.');
    if (!Number.isFinite(item.start) || !Number.isFinite(item.end) || item.start < 0 || item.end > 86400 || item.end <= item.start || item.end - item.start > 600) throw new Error('Indique un passage valide de 10 minutes maximum.');
    draft.items.push(item); changed(); render(); status('Extrait ajouté. Enregistre la séance pour le conserver.');
  }
  $('session-title').addEventListener('input', e => { draft.title = e.target.value; changed(); });
  $('session-objective').addEventListener('input', e => { draft.objective = e.target.value; changed(); });
  $('session-form').addEventListener('submit', guard(save));
  $('session-clip-form').addEventListener('submit', guard(() => add({match_id: Number($('clip-match').value), title: $('clip-title').value, start: Number($('clip-start').value), end: Number($('clip-end').value), note: ''})));
  document.querySelectorAll('[data-add-clip]').forEach(b => b.addEventListener('click', guard(() => add({match_id: Number(b.dataset.match), title: b.dataset.title, start: Number(b.dataset.start), end: Number(b.dataset.end), note: ''}))));
  $('session-list').addEventListener('change', guard(async () => {
    if (dirty && !confirm('Abandonner les modifications non enregistrées ?')) { $('session-list').value = draft.id || ''; return; }
    const id = $('session-list').value;
    draft = id ? await api(`/${id}`) : {title: '', objective: '', items: [], revision: 1};
    dirty = false; closePresentation(); render(); status(id ? 'Séance chargée.' : 'Nouvelle séance.');
  }));
  $('session-new').addEventListener('click', () => { $('session-list').value = ''; $('session-list').dispatchEvent(new Event('change')); });
  $('session-delete').addEventListener('click', guard(async () => {
    if (!draft.id || !confirm('Supprimer cette séance enregistrée ?')) return;
    await api(`/${draft.id}`, {method: 'DELETE'}); draft = {title: '', objective: '', items: [], revision: 1};
    dirty = false; closePresentation(); render(); await list(); status('Séance supprimée.');
  }));
  $('session-present').addEventListener('click', guard(async () => {
    if (!draft.items.length) throw new Error('Ajoute au moins un extrait.');
    if (dirty || !draft.id) await save();
    draft = await api(`/${draft.id}`); index = 0; present(); $('session-presentation').scrollIntoView({behavior: 'smooth'});
  }));
  $('presentation-prev').addEventListener('click', () => { if (index > 0) { index--; present(); } });
  $('presentation-next').addEventListener('click', () => { if (index < draft.items.length - 1) { index++; present(); } });
  $('presentation-close').addEventListener('click', closePresentation);
  window.addEventListener('beforeunload', e => { if (dirty) { e.preventDefault(); e.returnValue = ''; } });
  render(); list().catch(error => status(error.message));
})();
