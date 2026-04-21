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
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1920,1080'],
    protocolTimeout: 300000
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1920, height: 1080 });

  page.on('console', msg => {
    const txt = msg.text();
    if (txt.includes('HexViz') || txt.includes('Rendered') || txt.includes('hex cells')) {
      console.log('[BROWSER]', txt);
    }
  });

  await page.goto('http://localhost:8501', { waitUntil: 'networkidle2', timeout: 120000 });
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
    await sleep(20000);
  }

  // Click Maps Studio
  await page.evaluate(() => {
    for (const tab of document.querySelectorAll('[role="tab"]'))
      if (tab.textContent.trim() === 'Maps Studio') { tab.click(); return; }
  });

  // Wait for data
  let mapFrame = null;
  for (let tick = 0; tick < 8; tick++) {
    await sleep(10000);
    for (const frame of page.frames()) {
      try {
        const info = await frame.evaluate(() => {
          if (typeof L === 'undefined' || !window.__HEXBIN_DATA__) return null;
          return window.__HEXBIN_DATA__.length;
        });
        if (info > 0) { mapFrame = frame; break; }
      } catch(e) {}
    }
    if (mapFrame) break;
    console.log(`[${(tick+1)*10}s] Loading...`);
  }

  if (!mapFrame) {
    console.log('TIMEOUT');
    await browser.close();
    return;
  }

  // Debug: check _hexCellsByHub state
  const debugInfo = await mapFrame.evaluate(() => {
    const result = {};
    result.hexCellsByHubKeys = Object.keys(typeof _hexCellsByHub !== 'undefined' ? _hexCellsByHub : {}).length;
    result.hubRegistryKeys = Object.keys(hubRegistry).length;
    result.hubNameToIdKeys = Object.keys(typeof _hubNameToId !== 'undefined' ? _hubNameToId : {}).length;

    // Find a hub that has hex cells
    const hexHubs = Object.keys(_hexCellsByHub || {});
    if (hexHubs.length > 0) {
      const firstHid = hexHubs[0];
      result.sampleHubId = firstHid;
      result.sampleHubName = hubRegistry[firstHid] ? hubRegistry[firstHid].name : 'N/A';
      result.sampleCellCount = _hexCellsByHub[firstHid].length;
    }

    // Try rendering hexbins for first hub with data
    if (hexHubs.length > 0) {
      const hid = hexHubs[0];
      focusHub(hid);
      // renderHubHexbins should have been called by focusHub
      result.awbLayersAfterFocus = awbLayerGroups[hid] ? awbLayerGroups[hid].getLayers().length : -1;
    }

    return result;
  });
  console.log('Debug:', JSON.stringify(debugInfo));

  await sleep(3000);
  let fp = nextFile('hexbin-test');
  await page.screenshot({ path: fp, fullPage: false });
  console.log('Screenshot:', fp);

  // Zoom in
  await mapFrame.evaluate(() => { if(window.map) map.setZoom(map.getZoom()+2); });
  await sleep(2000);
  fp = nextFile('hexbin-zoomed');
  await page.screenshot({ path: fp, fullPage: false });
  console.log('Zoomed:', fp);

  await browser.close();
  console.log('Done!');
})();
