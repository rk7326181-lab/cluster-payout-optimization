import puppeteer from 'puppeteer';
import { existsSync, mkdirSync, readdirSync } from 'fs';
import { join } from 'path';

const dir = './temporary screenshots';
if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
function getFilename(lbl) {
  const n = readdirSync(dir).filter(f => f.startsWith('screenshot-')).length + 1;
  return lbl ? `screenshot-${n}-${lbl}.png` : `screenshot-${n}.png`;
}
async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

(async () => {
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1920,1080']
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1920, height: 1080 });

  // Capture console errors
  page.on('console', msg => {
    if (msg.type() === 'error' || msg.type() === 'warning') {
      console.log(`[${msg.type()}] ${msg.text()}`);
    }
  });
  page.on('pageerror', err => console.log(`[PAGE ERROR] ${err.message}`));

  await page.goto('http://localhost:8501', { waitUntil: 'networkidle2', timeout: 60000 });
  await sleep(3000);

  // Login
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

  // Click Maps Studio tab
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
    // Check AWB data and hexbin layer state
    const diag = await mapFrame.evaluate(() => {
      const awbData = window.__AWB_DATA__;
      const awbKeys = Object.keys(awbLayerGroups);
      const layerCounts = {};
      awbKeys.forEach(k => {
        let count = 0;
        awbLayerGroups[k].eachLayer(() => count++);
        layerCounts[k] = count;
      });
      // Check if hexBinPoints exists
      const hasFn = typeof hexBinPoints === 'function';
      const hasHV = typeof hexVertices === 'function';
      const hasHC = typeof hexColor === 'function';
      return {
        awbDataLen: awbData ? awbData.length : 0,
        awbGroupKeys: awbKeys.length,
        layerCounts: layerCounts,
        totalLayers: Object.values(layerCounts).reduce((s, v) => s + v, 0),
        hasFunctions: { hexBinPoints: hasFn, hexVertices: hasHV, hexColor: hasHC },
        hubCount: Object.keys(hubRegistry).length,
        awbVisible: awbVisible
      };
    });
    console.log('Diagnostic:', JSON.stringify(diag, null, 2));

    // Toggle AWB and check
    await mapFrame.evaluate(() => { toggleAWBLayer(); });
    await sleep(2000);

    const diag2 = await mapFrame.evaluate(() => {
      return { awbVisible: awbVisible };
    });
    console.log('After toggle:', JSON.stringify(diag2));

    // Zoom to area and screenshot
    await mapFrame.evaluate(() => { map.setView([26.14, 91.77], 12); });
    await sleep(4000);

    let fp = join(dir, getFilename('debug-hexbins'));
    await page.screenshot({ path: fp, fullPage: false });
    console.log(`Screenshot: ${fp}`);
  }

  await browser.close();
})();
