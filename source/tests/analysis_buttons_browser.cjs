/** Real Chromium navigation for the coach's primary match analysis buttons.
 * Reuses authenticated browser/context from the normal mobile regression.
 */
module.exports = async (page, base, assert) => {
  await page.goto(base + '/matches/new', {waitUntil:'networkidle'});
  assert(await page.locator('#quickYoutubeAnalysis').isVisible(),
    'YouTube quick-start is not visible');
  assert(await page.locator('#quickFileAnalysis').isVisible(),
    'MP4 quick-start is not visible');
  assert(await page.locator('#quickReports').isVisible(),
    'Saved reports quick-start is not visible');

  await page.locator('#quickFileAnalysis').click();
  assert(await page.locator('#phoneFilePanel').isVisible(), 'Mobile MP4 source panel not shown');
  assert(await page.locator('#phoneVideoFile').isEnabled(), 'Mobile MP4 input disabled');
  assert(await page.locator('#phoneAnalyzeSubmit').isEnabled(), 'Mobile MP4 submit disabled');
  await page.locator('#quickYoutubeAnalysis').click();
  assert(await page.locator('#phoneLinkPanel').isVisible(), 'Mobile YouTube source panel not shown');
  assert(await page.locator('#phoneVideoUrl').isEnabled(), 'Mobile YouTube URL disabled');

  await page.setViewportSize({width:1280,height:850});
  await page.reload({waitUntil:'networkidle'});
  await page.locator('#quickFileAnalysis').click();
  assert(await page.locator('#desktopFilePanel').isVisible(), 'Desktop MP4 source not shown');
  assert(await page.locator('#desktopVideoFile').isEnabled(), 'Desktop MP4 disabled');
  assert(await page.locator('#desktopFileAnalyzeSubmit').isEnabled(), 'Desktop file action disabled');
  assert(!(await page.locator('#desktopAnalyzeSubmit').isVisible()), 'Wrong YouTube button remains visible');
  await page.locator('#quickYoutubeAnalysis').click();
  assert(await page.locator('#desktopLinkPanel').isVisible(), 'Desktop YouTube panel not shown');
  assert(await page.locator('#desktopAnalyzeSubmit').isEnabled(), 'Desktop YouTube submit disabled');
  assert(!(await page.locator('#desktopFileAnalyzeSubmit').isVisible()), 'Wrong MP4 button remains visible');
  await page.locator('#quickReports').click();
  await page.waitForURL('**/analysis-history');

  // Real registered account avoids a demo account's upload/annotation limits.
  const email='ui-actions-'+Date.now()+'-'+Math.floor(Math.random()*1e6)+'@example.com';
  const signup=await page.request.post(base+'/register',{
    form:{email,password:'Password123!'},maxRedirects:0
  });
  assert(signup.status()===303,'Cannot register browser test account: '+signup.status());
  const created=await page.request.post(base+'/analysis/url/create',{
    form:{team_name:'UX Stop Test',opponent:'UX Visitor',
      video_url:'https://www.youtube.com/watch?v=f_WzRHjybgU',input_device:'phone'},
    maxRedirects:0
  });
  assert(created.status()===303,'Match creation failed: '+created.status());
  const location=created.headers()['location']||'';
  const id=(location.match(/\/matches\/(\d+)\//)||[])[1];
  assert(id,'Match creation did not return match ID');
  await page.goto(base+'/matches/'+id+'/analysis/browser-capture',{waitUntil:'networkidle'});
  assert(await page.locator('#finishCaptureAnytime').isVisible(),
    'Finish and report is hidden when capture not started');
  assert(await page.locator('#viewCaptureReport').isVisible(),'Partial report link hidden');
  await page.locator('#finishCaptureAnytime').click();
  await page.waitForURL('**/analysis/result?capture_not_started=1',{timeout:15000});
  assert(await page.locator('#reportQuickActions').isVisible(), 'Report quick actions missing');
  assert(await page.locator('#quickTagMatch').isVisible(), 'Analyze action hidden');
  assert(await page.locator('#quickShowStatistics').isVisible(), 'Statistics action hidden');
  await page.locator('#quickAddPart').click();
  assert(page.url().endsWith('#sources'), 'Add-quarter action does not navigate to video import');
  assert(await page.locator('#addMatchPartForm').count()===1, 'Quarter file form missing');
  await page.locator('#quickTagMatch').click();
  assert(page.url().endsWith('#annotation'), 'Analyze action does not navigate to video review');

  await page.setViewportSize({width:390,height:844});
  await page.reload({waitUntil:'networkidle'});
  const dock=page.locator('#reportQuickActions');
  assert(await dock.isVisible(),'Mobile report actions not visible');
  const pos=await dock.evaluate(el=>getComputedStyle(el).position);
  assert(pos==='fixed','Report action dock does not stay on-screen on mobile');
  assert(await page.locator('#quickDownloadReport').isEnabled(), 'Open report disabled');
  console.log('ANALYZE_BUTTONS_BROWSER_OK: mobile/desktop import choices, stop and report, sticky shortcuts');
};
