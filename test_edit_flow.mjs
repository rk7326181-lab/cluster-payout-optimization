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
    // Find ASK_Asika hub and enter edit mode
    const hubId = await mapFrame.evaluate(() => {
      const h = Object.values(hubRegistry).find(h => h.name === 'ASK_Asika');
      return h ? h.id : null;
    });

    if (hubId) {
      // Enable AWB hexbins first
      await mapFrame.evaluate(() => { toggleAWBLayer(); });
      await sleep(1000);

      // Enter edit mode for this hub
      await mapFrame.evaluate((hid) => { enterHubEditMode(hid); }, hubId);
      await sleep(3000);

      // Screenshot: Edit mode active with edit bar visible
      let fp = join(dir, getFilename('edit-mode-active'));
      await page.screenshot({ path: fp, fullPage: false });
      console.log(`Screenshot: ${fp}`);

      // Save and compare (triggers the comparison panel)
      await mapFrame.evaluate(() => { saveHubEdit(); });
      await sleep(2000);

      // Screenshot: Comparison panel showing before/after
      fp = join(dir, getFilename('comparison-panel'));
      await page.screenshot({ path: fp, fullPage: false });
      console.log(`Screenshot: ${fp}`);

      // Also test polygon edit popup
      await mapFrame.evaluate(() => { closeCompare(); });
      await sleep(500);

      // Click a polygon to edit its properties
      await mapFrame.evaluate(() => {
        const hlg = hubLayerGroups[Object.keys(hubLayerGroups)[0]];
        if (hlg && hlg.geoJsonLayer) {
          hlg.geoJsonLayer.eachLayer(layer => {
            if (layer.getLatLngs && !layer._clickedTest) {
              layer._clickedTest = true;
              const center = layer.getBounds().getCenter();
              map.setView(center, 13);
              setTimeout(() => layer.fire('click', { latlng: center }), 1000);
              throw 'break';
            }
          });
        }
      }).catch(() => {});
      await sleep(3000);

      fp = join(dir, getFilename('polygon-edit'));
      await page.screenshot({ path: fp, fullPage: false });
      console.log(`Screenshot: ${fp}`);
    }
  }

  await browser.close();
})();
