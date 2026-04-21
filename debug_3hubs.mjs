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

  // Check the 3 hubs in JavaScript
  const hubReport = await mapFrame.evaluate(() => {
    const targets = ['SIOB_Samakhiali', 'BEF_Kunkuri', 'PUL_RampuraJS'];
    const results = {};
    const allHubs = Object.values(hubRegistry);
    for (const name of targets) {
      const h = allHubs.find(x => x.name === name);
      if (!h) { results[name] = { found: false }; continue; }
      // Check feature-level data
      let featAwb = 0, featCost = 0, featDetails = [];
      const hlg = hubLayerGroups[h.id];
      if (hlg && hlg.geoJsonLayer) {
        hlg.geoJsonLayer.eachLayer(layer => {
          const p = layer._featureProps || {};
          const awb = p.awb_count || 0;
          const cost = p.total_cost || 0;
          featAwb += awb;
          featCost += cost;
          featDetails.push({ cc: p.cluster_code, pin: p.pincode, awb, cost, rate: p.rate_num });
        });
      }
      results[name] = {
        found: true,
        id: h.id,
        awbCount: h.awbCount,
        totalCost: h.totalCost,
        clusterCount: h.clusterCount,
        featAwb,
        featCost,
        featDetails: featDetails.slice(0, 5)
      };
    }
    return results;
  });

  console.log('=== 3 HUBS IN BROWSER ===');
  for (const [name, data] of Object.entries(hubReport)) {
    console.log(`\n--- ${name} ---`);
    if (!data.found) { console.log('  NOT FOUND in hubRegistry'); continue; }
    console.log(`  Hub AWB: ${data.awbCount}  Cost: ${data.totalCost}  Clusters: ${data.clusterCount}`);
    console.log(`  Feature-level AWB: ${data.featAwb}  Cost: ${data.featCost}`);
    console.log(`  Sample features:`);
    data.featDetails.forEach(f => {
      console.log(`    ${f.cc} | pin=${f.pin} | awb=${f.awb} | cost=${f.cost} | rate=${f.rate}`);
    });
  }

  // Now screenshot each hub focused
  for (const name of ['SIOB_Samakhiali', 'BEF_Kunkuri', 'PUL_RampuraJS']) {
    await mapFrame.evaluate((n) => {
      const panel = document.getElementById('hubPanel');
      if (panel) panel.classList.add('show');
      const h = Object.values(hubRegistry).find(x => x.name === n);
      if (h) focusHub(h.id);
    }, name);
    await sleep(5000);
    const fp = nextFile(name);
    await page.screenshot({ path: fp, fullPage: false });
    console.log(`\nScreenshot ${name}: ${fp}`);
  }

  await browser.close();
  console.log('\nDone!');
})();
