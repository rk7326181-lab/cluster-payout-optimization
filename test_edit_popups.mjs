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
    // Zoom to a hub area
    await mapFrame.evaluate(() => { map.setView([12.97, 77.59], 12); });
    await sleep(5000);

    // Screenshot: zoomed view with cost labels visible
    let fp = join(dir, getFilename('zoomed-labels'));
    await page.screenshot({ path: fp, fullPage: false });
    console.log(`Screenshot: ${fp}`);

    // Click on a polygon to test editable popup
    await mapFrame.evaluate(() => {
      // Find the first hub polygon layer and trigger click
      const hubIds = Object.keys(hubLayerGroups);
      if (hubIds.length > 0) {
        const hlg = hubLayerGroups[hubIds[0]];
        if (hlg && hlg.geoJsonLayer) {
          hlg.geoJsonLayer.eachLayer(layer => {
            if (layer.getLatLngs && !layer._clickedOnce) {
              layer._clickedOnce = true;
              const bounds = layer.getBounds();
              const center = bounds.getCenter();
              map.setView(center, 13);
              setTimeout(() => {
                layer.fire('click', { latlng: center });
              }, 1000);
              throw 'break';
            }
          });
        }
      }
    }).catch(() => {});
    await sleep(3000);

    // Screenshot: polygon edit popup
    fp = join(dir, getFilename('polygon-edit-popup'));
    await page.screenshot({ path: fp, fullPage: false });
    console.log(`Screenshot: ${fp}`);

    // Close popup and click on a hub marker
    await mapFrame.evaluate(() => {
      map.closePopup();
      // Find first hub marker and click it
      const hubIds = Object.keys(hubLayerGroups);
      for (const hid of hubIds) {
        const h = hubRegistry[hid];
        if (h && h.lat && h.lng) {
          map.setView([h.lat, h.lng], 13);
          // Find the marker in the layer group
          const hlg = hubLayerGroups[hid];
          if (hlg && hlg.layerGroup) {
            hlg.layerGroup.eachLayer(m => {
              if (m._hubIdRef && !m._clickedOnce) {
                m._clickedOnce = true;
                setTimeout(() => m.fire('click', { latlng: m.getLatLng() }), 1000);
                throw 'break';
              }
            });
          }
        }
      }
    }).catch(() => {});
    await sleep(3000);

    // Screenshot: hub marker edit popup
    fp = join(dir, getFilename('hub-edit-popup'));
    await page.screenshot({ path: fp, fullPage: false });
    console.log(`Screenshot: ${fp}`);

    // Close popup, zoom to show fullscreen button area
    await mapFrame.evaluate(() => {
      map.closePopup();
      map.setView([12.97, 77.59], 11);
    });
    await sleep(3000);

    // Screenshot: showing zoom controls with fullscreen button
    fp = join(dir, getFilename('zoom-controls'));
    await page.screenshot({ path: fp, fullPage: false });
    console.log(`Screenshot: ${fp}`);
  } else {
    console.log('Maps Studio frame not found');
  }

  await browser.close();
})();
