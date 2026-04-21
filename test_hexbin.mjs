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
  await sleep(15000);

  let mapFrame = null;
  for (const frame of page.frames()) {
    const title = await frame.title().catch(() => '');
    if (title.includes('Maps Studio')) { mapFrame = frame; break; }
  }

  if (mapFrame) {
    // 1. Zoom to Bangalore area with labels visible
    await mapFrame.evaluate(() => { map.setView([12.97, 77.59], 11); });
    await sleep(5000);

    let fp = join(dir, getFilename('labels-visible'));
    await page.screenshot({ path: fp, fullPage: false });
    console.log(`Screenshot: ${fp}`);

    // 2. Toggle AWB hexbins on
    await mapFrame.evaluate(() => {
      // Call toggleAWBLayer
      toggleAWBLayer();
    });
    await sleep(3000);

    fp = join(dir, getFilename('hexbins-bangalore'));
    await page.screenshot({ path: fp, fullPage: false });
    console.log(`Screenshot: ${fp}`);

    // 3. Zoom in closer to see hexbin detail
    await mapFrame.evaluate(() => { map.setView([12.97, 77.59], 13); });
    await sleep(3000);

    fp = join(dir, getFilename('hexbins-close'));
    await page.screenshot({ path: fp, fullPage: false });
    console.log(`Screenshot: ${fp}`);

    // 4. View a different hub area (Guwahati)
    await mapFrame.evaluate(() => { map.setView([26.14, 91.77], 12); });
    await sleep(4000);

    fp = join(dir, getFilename('hexbins-guwahati'));
    await page.screenshot({ path: fp, fullPage: false });
    console.log(`Screenshot: ${fp}`);

    // 5. India-wide view with polygons
    await mapFrame.evaluate(() => {
      toggleAWBLayer(); // turn off hexbins for cleaner view
      map.setView([20.5, 78.5], 5);
    });
    await sleep(4000);

    fp = join(dir, getFilename('india-polygons'));
    await page.screenshot({ path: fp, fullPage: false });
    console.log(`Screenshot: ${fp}`);

  } else {
    console.log('Maps Studio frame not found');
  }

  await browser.close();
})();
