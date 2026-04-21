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

  // Login if needed
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
  console.log('Waiting for Maps Studio to load...');
  await sleep(25000);

  // Find the map iframe
  let mapFrame = null;
  const iframes = await page.$$('iframe');
  for (const iframe of iframes) {
    const f = await iframe.contentFrame();
    if (f) {
      // Check if this frame has the map
      const hasMap = await f.evaluate(() => typeof map !== 'undefined' && typeof hubRegistry !== 'undefined').catch(() => false);
      if (hasMap) { mapFrame = f; break; }
    }
  }

  if (!mapFrame && iframes.length > 0) {
    // Fallback: use the last iframe (usually the map)
    mapFrame = await iframes[iframes.length - 1].contentFrame();
  }

  console.log('Map frame found:', !!mapFrame);

  if (mapFrame) {
    // Check hub data loaded
    const hubCount = await mapFrame.evaluate(() => {
      return Object.keys(hubRegistry || {}).length;
    }).catch(() => 0);
    console.log('Hubs loaded:', hubCount);

    // Open the Hub Filter & Edit panel
    await mapFrame.evaluate(() => {
      const panel = document.getElementById('hubPanel');
      if (panel) panel.classList.add('show');
    });
    await sleep(2000);

    // Zoom to India view
    await mapFrame.evaluate(() => { map.setView([22.5, 79.5], 5); });
    await sleep(5000);
  }

  // Screenshot 1: Full India view with hub panel open
  let fp = nextFile('india-with-hubpanel');
  await page.screenshot({ path: fp, fullPage: false });
  console.log('Screenshot:', fp);

  if (mapFrame) {
    // Zoom to Bangalore
    await mapFrame.evaluate(() => { map.setView([12.97, 77.59], 11); });
    await sleep(5000);
  }

  // Screenshot 2: Bangalore zoom
  fp = nextFile('bangalore-with-hubpanel');
  await page.screenshot({ path: fp, fullPage: false });
  console.log('Screenshot:', fp);

  if (mapFrame) {
    // Zoom to Delhi NCR
    await mapFrame.evaluate(() => { map.setView([28.61, 77.23], 10); });
    await sleep(5000);
  }

  // Screenshot 3: Delhi
  fp = nextFile('delhi-with-hubpanel');
  await page.screenshot({ path: fp, fullPage: false });
  console.log('Screenshot:', fp);

  if (mapFrame) {
    // Scroll hub list to show hubs with AWB data
    await mapFrame.evaluate(() => {
      const list = document.getElementById('hubList');
      if (list) list.scrollTop = 600;
    });
    await sleep(1000);

    // Zoom to Mumbai
    await mapFrame.evaluate(() => { map.setView([19.08, 72.88], 11); });
    await sleep(5000);
  }

  // Screenshot 4: Mumbai + scrolled hub list
  fp = nextFile('mumbai-hublist-scrolled');
  await page.screenshot({ path: fp, fullPage: false });
  console.log('Screenshot:', fp);

  await browser.close();
  console.log('Done!');
})();
