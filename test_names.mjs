import puppeteer from 'puppeteer';
async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
(async () => {
  const browser = await puppeteer.launch({ headless: true, args: ['--no-sandbox'] });
  const page = await browser.newPage();
  await page.goto('http://localhost:8501', { waitUntil: 'networkidle2', timeout: 60000 });
  await sleep(3000);
  const inputs = await page.$$('input');
  if (inputs.length >= 2) {
    await inputs[0].click({ clickCount: 3 }); await inputs[0].type('admin@shadowfax.in');
    await inputs[1].click({ clickCount: 3 }); await inputs[1].type('shadowfax2026');
    await sleep(500);
    await page.evaluate(() => {
      for (const btn of document.querySelectorAll('button'))
        if (btn.textContent.toLowerCase().includes('sign in')) { btn.click(); return; }
    });
    await sleep(12000);
  }
  await page.evaluate(() => {
    for (const tab of document.querySelectorAll('[role="tab"]'))
      if (tab.textContent.includes('Maps Studio')) { tab.click(); return; }
  });
  await sleep(18000);

  let mapFrame = null;
  for (const frame of page.frames()) {
    const title = await frame.title().catch(() => '');
    if (title.includes('Maps Studio')) { mapFrame = frame; break; }
  }
  if (mapFrame) {
    const result = await mapFrame.evaluate(() => {
      const awbData = window.__AWB_DATA__ || [];
      const awbHubNames = [...new Set(awbData.map(a => a.hub))].slice(0, 20);
      const registryNames = Object.values(hubRegistry).map(h => h.name).slice(0, 20);
      // Try matching first AWB hub name
      const firstAwb = awbHubNames[0] || '';
      const match = Object.values(hubRegistry).find(h => h.name && h.name.toLowerCase() === firstAwb.toLowerCase());
      return { awbHubNames, registryNames, firstAwb, matchFound: !!match, matchName: match?.name || null };
    });
    console.log('AWB hub names (first 20):', result.awbHubNames);
    console.log('Registry hub names (first 20):', result.registryNames);
    console.log('First AWB name:', result.firstAwb, '-> match:', result.matchFound, result.matchName);
  }
  await browser.close();
})();
