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
    // Check which hubs have AWB hexbin layers
    const hubInfo = await mapFrame.evaluate(() => {
      const result = [];
      Object.entries(awbLayerGroups).forEach(([hid, lg]) => {
        let count = 0;
        lg.eachLayer(() => count++);
        if (count > 0) {
          const h = hubRegistry[hid];
          result.push({ id: hid, name: h?.name, lat: h?.lat, lng: h?.lng, layerCount: count });
        }
      });
      return result;
    });
    console.log('Hubs with hexbin layers:', JSON.stringify(hubInfo, null, 2));

    if (hubInfo.length > 0) {
      // Enable AWB hexbins
      await mapFrame.evaluate(() => { toggleAWBLayer(); });
      await sleep(2000);

      // Zoom to first hub with hexbins
      const firstHub = hubInfo[0];
      const lat = firstHub.lat || 19.6;
      const lng = firstHub.lng || 84.6;
      console.log(`Zooming to ${firstHub.name} at ${lat}, ${lng}`);

      await mapFrame.evaluate((lat, lng) => { map.setView([lat, lng], 12); }, lat, lng);
      await sleep(4000);

      let fp = join(dir, getFilename('hexbin-hub1'));
      await page.screenshot({ path: fp, fullPage: false });
      console.log(`Screenshot: ${fp}`);

      // Zoom closer
      await mapFrame.evaluate((lat, lng) => { map.setView([lat, lng], 13); }, lat, lng);
      await sleep(3000);

      fp = join(dir, getFilename('hexbin-hub1-close'));
      await page.screenshot({ path: fp, fullPage: false });
      console.log(`Screenshot: ${fp}`);

      // Also open hub panel to show legend
      await mapFrame.evaluate(() => {
        const btn = document.getElementById('btn-hubfilter');
        if (btn) btn.click();
      });
      await sleep(1500);

      fp = join(dir, getFilename('hexbin-with-panel'));
      await page.screenshot({ path: fp, fullPage: false });
      console.log(`Screenshot: ${fp}`);

      // If second hub exists, show it too
      if (hubInfo.length > 1) {
        const h2 = hubInfo[1];
        await mapFrame.evaluate((lat, lng) => { map.setView([lat, lng], 12); }, h2.lat || 21.2, h2.lng || 81.6);
        await sleep(4000);
        fp = join(dir, getFilename('hexbin-hub2'));
        await page.screenshot({ path: fp, fullPage: false });
        console.log(`Screenshot: ${fp}`);
      }
    } else {
      console.log('No hubs have hexbin layers!');
    }
  }

  await browser.close();
})();
