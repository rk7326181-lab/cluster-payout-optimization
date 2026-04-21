import puppeteer from 'puppeteer';
async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
(async () => {
  const browser = await puppeteer.launch({ headless: true, args: ['--no-sandbox', '--window-size=1920,1080'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1920, height: 1080 });
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
  // Navigate to Maps Studio
  await page.evaluate(() => {
    for (const tab of document.querySelectorAll('[role="tab"]'))
      if (tab.textContent.includes('Maps Studio')) { tab.click(); return; }
  });
  await sleep(15000);

  // Capture the page text to find our debug line
  const text = await page.evaluate(() => document.body.innerText);
  const debugLine = text.split('\n').find(l => l.includes('AWB hub sample'));
  console.log('Debug line:', debugLine || 'NOT FOUND');

  // Also check the AWB data in the iframe
  let mapFrame = null;
  for (const frame of page.frames()) {
    const title = await frame.title().catch(() => '');
    if (title.includes('Maps Studio')) { mapFrame = frame; break; }
  }
  if (mapFrame) {
    const awbCheck = await mapFrame.evaluate(() => {
      const awb = window.__AWB_DATA__ || [];
      const nonEmpty = awb.filter(a => a.hub && a.hub.length > 0);
      return { total: awb.length, nonEmptyHub: nonEmpty.length, sample: awb.slice(0, 2) };
    });
    console.log('AWB in iframe:', JSON.stringify(awbCheck));
  }
  await browser.close();
})();
