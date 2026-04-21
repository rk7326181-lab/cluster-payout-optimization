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
      // Get first 3 records with ALL their fields
      const samples = awbData.slice(0, 3).map(a => ({...a}));
      // Also get keys
      const keys = awbData.length > 0 ? Object.keys(awbData[0]) : [];
      // Check hub field specifically
      const hubValues = awbData.slice(0, 10).map(a => ({ hub: a.hub, hubType: typeof a.hub }));
      return { samples, keys, hubValues, totalLen: awbData.length };
    });
    console.log('AWB keys:', result.keys);
    console.log('AWB samples:', JSON.stringify(result.samples, null, 2));
    console.log('Hub values:', JSON.stringify(result.hubValues));
  }
  await browser.close();
})();
