import puppeteer from 'puppeteer';
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
  console.log(`Found ${iframes.length} iframes`);
  for (const iframe of iframes) {
    const f = await iframe.contentFrame();
    if (f) {
      const check = await f.evaluate(() => {
        return { hasHub: typeof hubRegistry !== 'undefined', hasMap: typeof map !== 'undefined', title: document.title };
      }).catch(() => ({ hasHub: false, hasMap: false, title: 'err' }));
      console.log(`  iframe: title="${check.title}" hasHub=${check.hasHub} hasMap=${check.hasMap}`);
      if (check.hasHub) { mapFrame = f; break; }
    }
  }
  // Fallback: use last iframe
  if (!mapFrame && iframes.length > 0) {
    const lastF = await iframes[iframes.length - 1].contentFrame();
    if (lastF) mapFrame = lastF;
    console.log('Using fallback (last iframe)');
  }

  if (mapFrame) {
    // Check hub data in detail
    const report = await mapFrame.evaluate(() => {
      const hubs = Object.values(hubRegistry);
      const totalHubs = hubs.length;
      const hubsWithAwb = hubs.filter(h => h.awbCount > 0).length;
      const hubsWithCost = hubs.filter(h => h.totalCost > 0).length;
      const totalAwb = hubs.reduce((s, h) => s + h.awbCount, 0);
      const totalCost = hubs.reduce((s, h) => s + h.totalCost, 0);

      // Check feature-level data for first 5 hubs
      const sampleHubs = hubs.slice(0, 10).map(h => {
        let featAwb = 0, featCost = 0;
        const hlg = hubLayerGroups[h.id];
        let layerAwb = 0, layerCost = 0;
        if (hlg && hlg.geoJsonLayer) {
          hlg.geoJsonLayer.eachLayer(layer => {
            const p = layer._featureProps || {};
            layerAwb += (p.awb_count || 0);
            layerCost += (p.total_cost || 0);
          });
        }
        h.features.forEach(f => {
          featAwb += (f.properties?.awb_count || 0);
          featCost += (f.properties?.total_cost || 0);
        });
        return {
          name: h.name,
          awbCount: h.awbCount,
          totalCost: h.totalCost,
          clusterCount: h.clusterCount,
          featAwb,
          featCost,
          layerAwb,
          layerCost
        };
      });

      // Check a few specific features
      const sampleFeatures = [];
      const clusterGJ = window.__CLUSTER_GEOJSON__;
      if (clusterGJ && clusterGJ.features) {
        for (let i = 0; i < Math.min(5, clusterGJ.features.length); i++) {
          const f = clusterGJ.features[i];
          sampleFeatures.push({
            hub: f.properties?.hub_name,
            cluster: f.properties?.cluster_code,
            pin: f.properties?.pincode,
            awb: f.properties?.awb_count,
            cost: f.properties?.total_cost,
            rate: f.properties?.rate_num
          });
        }
      }

      // Find hubs with ZERO AWB
      const zeroHubs = hubs.filter(h => h.awbCount === 0).map(h => h.name).slice(0, 20);

      return {
        totalHubs, hubsWithAwb, hubsWithCost, totalAwb, totalCost,
        sampleHubs, sampleFeatures, zeroHubs,
        geojsonFeatureCount: clusterGJ?.features?.length || 0
      };
    });

    console.log('=== HUB DATA REPORT ===');
    console.log(`Total Hubs: ${report.totalHubs}`);
    console.log(`Hubs with AWB > 0: ${report.hubsWithAwb}`);
    console.log(`Hubs with Cost > 0: ${report.hubsWithCost}`);
    console.log(`Total AWB: ${report.totalAwb.toLocaleString()}`);
    console.log(`Total Cost: ${report.totalCost.toLocaleString()}`);
    console.log(`GeoJSON Features: ${report.geojsonFeatureCount}`);
    console.log('');
    console.log('=== SAMPLE HUBS (first 10) ===');
    report.sampleHubs.forEach(h => {
      console.log(`  ${h.name}: awb=${h.awbCount} cost=${h.totalCost} clusters=${h.clusterCount} featAwb=${h.featAwb} layerAwb=${h.layerAwb}`);
    });
    console.log('');
    console.log('=== SAMPLE FEATURES (first 5 from GeoJSON) ===');
    report.sampleFeatures.forEach(f => {
      console.log(`  ${f.hub} | ${f.cluster} | pin=${f.pin} | awb=${f.awb} | cost=${f.cost} | rate=${f.rate}`);
    });
    console.log('');
    console.log(`=== ZERO-AWB HUBS (${report.zeroHubs.length}) ===`);
    report.zeroHubs.forEach(n => console.log(`  ${n}`));
  } else {
    console.log('ERROR: Map frame not found');
  }

  await browser.close();
})();
