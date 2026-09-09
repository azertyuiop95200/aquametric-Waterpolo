// Called by the existing mobile regression workflow against its disposable server.
module.exports = async function verifySessions(page, base, assert) {
  await page.goto(base + '/analysis/video-session-elite', {waitUntil: 'domcontentloaded'});
  await page.locator('#session-title').fill('Séance navigateur');
  await page.locator('#session-objective').fill('Observer les aides au centre');
  await page.locator('#session-form button[type=submit]').click();
  await page.locator('#session-status').filter({hasText: 'Séance enregistrée.'}).waitFor();
  const savedId = await page.locator('#session-list').inputValue();
  assert(savedId, 'saved session has no selected ID');
  await page.reload({waitUntil: 'domcontentloaded'});
  await page.locator(`#session-list option[value="${savedId}"]`).waitFor({state: 'attached'});
  await page.locator('#session-list').selectOption(savedId);
  await page.locator('#session-status').filter({hasText: 'Séance chargée.'}).waitFor();
  assert(await page.locator('#session-objective').inputValue() === 'Observer les aides au centre', 'session objective was not persisted');
  await page.locator('#session-objective').fill('Correction mise à jour');
  await page.locator('#session-form button[type=submit]').click();
  await page.locator('#session-status').filter({hasText: 'Séance enregistrée.'}).waitFor();
  const exported = await page.request.get(new URL(await page.locator('#session-export').getAttribute('href'), base).href);
  assert(exported.ok(), 'session export failed');
  assert((await exported.json()).objective === 'Correction mise à jour', 'export does not contain updated notes');
  page.once('dialog', dialog => dialog.accept());
  await page.locator('#session-delete').click();
  await page.locator('#session-status').filter({hasText: 'Séance supprimée.'}).waitFor();
  assert(await page.locator(`#session-list option[value="${savedId}"]`).count() === 0, 'deleted session remains in library');
  console.log('Saved video sessions: mobile create, reopen, update, export and delete OK');
};
