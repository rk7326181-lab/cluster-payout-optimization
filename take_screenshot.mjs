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

  // Screenshot 1: Dashboard with fixed sidebar
  let fp = join(dir, getFilename('sidebar-fixed'));
  await page.screenshot({ path: fp, fullPage: false });
  console.log(`Screenshot: ${fp}`);

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
    // Zoom to Bangalore area
    await mapFrame.evaluate(() => { map.setView([12.97, 77.59], 11); });
    await sleep(5000);

    // Screenshot 2: Map Studio with polygons visible
    fp = join(dir, getFilename('mapstudio-polygons'));
    await page.screenshot({ path: fp, fullPage: false });
    console.log(`Screenshot: ${fp}`);

    // Open hub panel
    await mapFrame.evaluate(() => {
      const btn = document.getElementById('btn-hubfilter');
      if (btn) btn.click();
    });
    await sleep(1500);

    // Screenshot 3: Hub filter panel open
    fp = join(dir, getFilename('mapstudio-hubpanel'));
    await page.screenshot({ path: fp, fullPage: false });
    console.log(`Screenshot: ${fp}`);

    // Close hub panel, open import/export
    await mapFrame.evaluate(() => {
      document.getElementById('hubPanel').classList.remove('show');
      const ieBtn = document.querySelector('[onclick="openIE()"]');
      if (ieBtn) ieBtn.click();
    });
    await sleep(1000);

    // Switch to export tab
    await mapFrame.evaluate(() => {
      const tabs = document.querySelectorAll('.tab-b');
      if (tabs.length > 1) tabs[1].click();
    });
    await sleep(500);

    // Screenshot 4: Export panel
    fp = join(dir, getFilename('mapstudio-export'));
    await page.screenshot({ path: fp, fullPage: false });
    console.log(`Screenshot: ${fp}`);

    // Close export, zoom to India view
    await mapFrame.evaluate(() => {
      document.getElementById('importExportPanel').classList.remove('show');
      map.setView([20.5, 78.5], 5);
    });
    await sleep(5000);

    // Screenshot 5: Full India view with all hub polygons
    fp = join(dir, getFilename('mapstudio-india'));
    await page.screenshot({ path: fp, fullPage: false });
    console.log(`Screenshot: ${fp}`);
  }

  await browser.close();
})();
