module.exports = async function verifyMobileLink(page, base, assert) {
  await page.goto(base + '/matches/new', {waitUntil: 'domcontentloaded'});
  await page.locator('#phoneVideoUrl').waitFor({state: 'visible'});
  assert(await page.locator('#phoneVideoUrl').isEnabled(), 'phone URL field disabled');
  assert(await page.locator('#phoneVideoFile').isDisabled(), 'hidden upload field is not disabled');
  await page.locator('[name=team_name]').fill('Équipe test mobile');
  await page.locator('[name=opponent]').fill('Adversaire test mobile');
  await page.locator('#phoneVideoUrl').fill('https://example.com/match-test');
  // Switching input modes must preserve the typed URL and avoid duplicate form fields.
  await page.locator('#phoneSource').selectOption('file');
  assert(await page.locator('#phoneVideoFile').isEnabled(), 'file selection unavailable');
  await page.locator('#phoneSource').selectOption('link');
  assert(await page.locator('#phoneVideoUrl').inputValue() === 'https://example.com/match-test', 'switching erased URL');
  await page.locator('#phoneLinkSubmit').click();
  await page.waitForURL(/\/matches\/\d+\/analysis\/result$/);
  assert(await page.locator('#mobileLinkSaved').isVisible(), 'saved link status missing');
  const matchId = page.url().match(/\/matches\/(\d+)/)[1];
  const exported = await page.request.get(base + `/matches/${matchId}/analysis/report.html`);
  assert(exported.ok(), 'portable report unavailable');
  const html = await exported.text();
  assert(html.includes('Vidéo identifiée mais non analysée'), 'report falsely claims pixel analysis');
  assert(html.includes('Non mesuré'), 'report invents sporting zeros');
  await page.reload({waitUntil:'domcontentloaded'});
  assert(await page.locator('#mobileLinkSaved').isVisible(), 'saved match did not survive reload');
  console.log('Mobile link: input, source switching, save, reopen and truthful report OK');
};
