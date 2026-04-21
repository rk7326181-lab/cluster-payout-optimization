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

  await page.goto('http://localhost:8501', { waitUntil: 'networkidle2', timeout: 60000 });
  await sleep(5000);

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
    await sleep(15000);
  }

  // Click Maps Studio tab
  await page.evaluate(() => {
    for (const tab of document.querySelectorAll('[role="tab"]'))
      if (tab.textContent.includes('Maps Studio')) { tab.click(); return; }
  });
  await sleep(25000);

  // Find the map iframe
  let mapFrame = null;
  const iframes = await page.$$('iframe');
  for (const iframe of iframes) {
    const f = await iframe.contentFrame();
    if (f) {
      const hasMap = await f.evaluate(() => typeof hubRegistry !== 'undefined').catch(() => false);
      if (hasMap) { mapFrame = f; break; }
    }
  }
  if (!mapFrame && iframes.length > 0) {
    mapFrame = await iframes[iframes.length - 1].contentFrame();
  }

  if (mapFrame) {
    // Open hub panel
    await mapFrame.evaluate(() => {
      const panel = document.getElementById('hubPanel');
      if (panel) panel.classList.add('show');
    });
    await sleep(1000);

    // Focus on a specific hub (BLR_Kadugodi - has lots of AWBs)
    await mapFrame.evaluate(() => {
      const hubs = Object.values(hubRegistry);
      // Find a hub with high AWB count
      const target = hubs.find(h => h.name.includes('Kadugodi')) || hubs.find(h => h.awbCount > 50000) || hubs[0];
      if (target) focusHub(target.id);
    });
    await sleep(5000);

    // Screenshot 1: Hub focused with summary card showing AWB and burn
    let fp = nextFile('hub-focused-summary');
    await page.screenshot({ path: fp, fullPage: false });
    console.log('Screenshot:', fp);

    // Click on a polygon to show popup
    await mapFrame.evaluate(() => {
      const hubs = Object.values(hubRegistry);
      const target = hubs.find(h => h.name.includes('Kadugodi')) || hubs.find(h => h.awbCount > 50000) || hubs[0];
      if (target) {
        const hlg = hubLayerGroups[target.id];
        if (hlg && hlg.geoJsonLayer) {
          hlg.geoJsonLayer.eachLayer(layer => {
            if (layer._featureProps && layer.getBounds) {
              const center = layer.getBounds().getCenter();
              openPolyEditPopup(layer, target);
              return;
            }
          });
        }
      }
    });
    await sleep(2000);

    // Screenshot 2: Polygon popup with AWB and burn data
    fp = nextFile('polygon-popup-awb');
    await page.screenshot({ path: fp, fullPage: false });
    console.log('Screenshot:', fp);

    // Now test a different hub - search for one
    await mapFrame.evaluate(() => {
      const hubs = Object.values(hubRegistry);
      const target = hubs.find(h => h.name.includes('Haldwani')) || hubs.find(h => h.name.includes('DEL_Okhla')) || hubs[5];
      if (target) focusHub(target.id);
    });
    await sleep(5000);

    // Screenshot 3: Another hub focused
    fp = nextFile('hub2-focused-summary');
    await page.screenshot({ path: fp, fullPage: false });
    console.log('Screenshot:', fp);

    // Click polygon on this hub too
    await mapFrame.evaluate(() => {
      const hubs = Object.values(hubRegistry);
      const target = hubs.find(h => h.name.includes('Haldwani')) || hubs.find(h => h.name.includes('DEL_Okhla')) || hubs[5];
      if (target) {
        const hlg = hubLayerGroups[target.id];
        if (hlg && hlg.geoJsonLayer) {
          let done = false;
          hlg.geoJsonLayer.eachLayer(layer => {
            if (!done && layer._featureProps && layer.getBounds) {
              openPolyEditPopup(layer, target);
              done = true;
            }
          });
        }
      }
    });
    await sleep(2000);

    // Screenshot 4: Polygon popup on second hub
    fp = nextFile('hub2-polygon-popup');
    await page.screenshot({ path: fp, fullPage: false });
    console.log('Screenshot:', fp);

    // Test burn mode
    await mapFrame.evaluate(() => {
      if (typeof switchColorMode === 'function') switchColorMode('burn');
    });
    await sleep(3000);

    // Zoom out to show burn colors
    await mapFrame.evaluate(() => { map.setView([20.5, 78.5], 5); });
    await sleep(5000);

    fp = nextFile('burn-mode-india');
    await page.screenshot({ path: fp, fullPage: false });
    console.log('Screenshot:', fp);

  } else {
    console.log('Map frame not found');
  }

  await browser.close();
  console.log('Done!');
})();
