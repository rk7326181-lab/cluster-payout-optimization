import puppeteer from 'puppeteer';
import { existsSync, mkdirSync, readdirSync } from 'fs';
import { join } from 'path';
const dir = './temporary screenshots';
if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
function nextFile(lbl) {
  const n = readdirSync(dir).filter(f => f.startsWith('screenshot-')).length + 1;
  return join(dir, lbl ? `screenshot-${n}-${lbl}.png` : `screenshot-${n}.png`);
}
const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1920,1080']
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1920, height: 1080 });

  // Capture console logs from the iframe
  page.on('console', msg => {
    if (msg.text().includes('HexViz')) console.log('[PAGE]', msg.text());
  });

  await page.goto('http://localhost:8501', { waitUntil: 'networkidle2', timeout: 60000 });
  await sleep(5000);
  const inputs = await page.$$('input');
  if (inputs.length >= 2) {
    await inputs[0].click({ clickCount: 3 }); await inputs[0].type('admin@shadowfax.in');
    await inputs[1].click({ clickCount: 3 }); await inputs[1].type('shadowfax2026');
    await sleep(500);
    await page.evaluate(() => {
      for (const btn of document.querySelectorAll('button'))
        if (btn.textContent.toLowerCase().includes('sign in')) { btn.click(); return; }
    });
    await sleep(15000);
  }
  await page.evaluate(() => {
    for (const tab of document.querySelectorAll('[role="tab"]'))
      if (tab.textContent.includes('Maps Studio')) { tab.click(); return; }
  });
  await sleep(25000);

  let mapFrame = null;
  const iframes = await page.$$('iframe');
  for (const iframe of iframes) {
    const f = await iframe.contentFrame();
    if (f) {
      const ok = await f.evaluate(() => typeof hubRegistry !== 'undefined').catch(() => false);
      if (ok) { mapFrame = f; break; }
    }
  }

  if (!mapFrame) { console.log('No map frame'); await browser.close(); return; }

  // Check hexbin data for the 3 hubs
  const hexReport = await mapFrame.evaluate(() => {
    const targets = ['SIOB_Samakhiali', 'BEF_Kunkuri', 'PUL_RampuraJS'];
    const allHubs = Object.values(hubRegistry);
    const results = {};
    const totalHexHubs = Object.keys(window._hexCellsByHub || {}).length;
    const totalHexCells = Object.values(window._hexCellsByHub || {}).reduce((s, cells) => s + cells.length, 0);

    for (const name of targets) {
      const h = allHubs.find(x => x.name === name);
      if (!h) { results[name] = { found: false }; continue; }
      const hexCells = (window._hexCellsByHub || {})[h.id] || [];
      results[name] = {
        found: true,
        id: h.id,
        awbCount: h.awbCount,
        hexCells: hexCells.length,
        hexSample: hexCells.slice(0, 3).map(c => ({ lat: c.lat, lng: c.lng, count: c.count, pin: c.pincode }))
      };
    }

    // Also check overall stats
    const hubsWithHex = Object.entries(window._hexCellsByHub || {}).filter(([, cells]) => cells.length > 0).length;

    return { totalHexHubs, totalHexCells, hubsWithHex, results };
  });

  console.log('=== HEXBIN FIX REPORT ===');
  console.log(`Total hubs with hexbin data: ${hexReport.hubsWithHex}`);
  console.log(`Total hex cells indexed: ${hexReport.totalHexCells}`);
  console.log('');

  for (const [name, data] of Object.entries(hexReport.results)) {
    console.log(`--- ${name} ---`);
    if (!data.found) { console.log('  NOT FOUND'); continue; }
    console.log(`  AWB count: ${data.awbCount}`);
    console.log(`  Hex cells: ${data.hexCells}`);
    if (data.hexSample.length > 0) {
      console.log(`  Sample cells:`);
      data.hexSample.forEach(c => console.log(`    lat=${c.lat} lng=${c.lng} count=${c.count} pin=${c.pin}`));
    }
  }

  // Screenshot each hub with AWB hexbin overlay
  for (const name of ['SIOB_Samakhiali', 'BEF_Kunkuri', 'PUL_RampuraJS']) {
    await mapFrame.evaluate((n) => {
      const panel = document.getElementById('hubPanel');
      if (panel) panel.classList.add('show');
      const h = Object.values(hubRegistry).find(x => x.name === n);
      if (h) {
        focusHub(h.id); // This triggers renderHubHexbins
      }
    }, name);
    await sleep(6000);

    // Toggle AWB layer on
    await mapFrame.evaluate(() => {
      if (!awbVisible && typeof toggleAWBLayer === 'function') toggleAWBLayer();
    });
    await sleep(2000);

    const fp = nextFile(name + '-AWB');
    await page.screenshot({ path: fp, fullPage: false });
    console.log(`\nScreenshot ${name}: ${fp}`);
  }

  await browser.close();
  console.log('\nDone!');
})();
