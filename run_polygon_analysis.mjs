import puppeteer from 'puppeteer';
import { existsSync, mkdirSync, readdirSync } from 'fs';
import { join } from 'path';

const dir = './temporary screenshots';
if (!existsSync(dir)) mkdirSync(dir, { recursive: true });

let shotN = readdirSync(dir).filter(f => f.startsWith('screenshot-')).length;
function getFilename(lbl) {
  shotN++;
  return lbl ? `screenshot-${shotN}-${lbl}.png` : `screenshot-${shotN}.png`;
}
async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function shot(page, label) {
  const fp = join(dir, getFilename(label));
  await page.screenshot({ path: fp, fullPage: false });
  console.log(`  [SCREENSHOT] ${label} -> ${fp}`);
  return fp;
}

async function scrollToText(page, text) {
  return page.evaluate((searchText) => {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      if (walker.currentNode.textContent.includes(searchText)) {
        const el = walker.currentNode.parentElement;
        let parent = el;
        while (parent) {
          const testId = parent.getAttribute('data-testid') || '';
          if (testId === 'stMain') {
            const rect = el.getBoundingClientRect();
            const parentRect = parent.getBoundingClientRect();
            parent.scrollTop += (rect.top - parentRect.top - 80);
            return true;
          }
          parent = parent.parentElement;
        }
        el.scrollIntoView({ block: 'start', behavior: 'instant' });
        return true;
      }
    }
    return false;
  }, text);
}

async function scrollMain(page, pos) {
  await page.evaluate((p) => {
    const main = document.querySelector('[data-testid="stMain"]');
    if (main) main.scrollTop = p;
  }, pos);
  await sleep(400);
}

(async () => {
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1920,1200']
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1920, height: 1200 });

  // Login
  console.log('Loading & logging in...');
  await page.goto('http://localhost:8501', { waitUntil: 'networkidle2', timeout: 60000 });
  await sleep(4000);
  const needsLogin = await page.evaluate(() => { for (const h of document.querySelectorAll('h2')) if (h.textContent.includes('Welcome Back')) return true; return false; });
  if (needsLogin) {
    await page.evaluate(() => {
      const ns = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
      for (const inp of document.querySelectorAll('input')) {
        if (inp.type === 'password') { ns.call(inp, 'shadowfax2026'); inp.dispatchEvent(new Event('input', {bubbles:true})); }
        else if (inp.getAttribute('aria-label')?.includes('Email')) { ns.call(inp, 'admin@shadowfax.in'); inp.dispatchEvent(new Event('input', {bubbles:true})); }
      }
    });
    await sleep(500);
    await page.evaluate(() => { for (const btn of document.querySelectorAll('button')) if (btn.textContent.includes('Sign In')) { btn.click(); return; } });
    await sleep(18000);
  }
  console.log('Login complete.\n');

  async function clickTab(text) {
    const tabs = await page.$$('[role="tab"]');
    for (const tab of tabs) {
      const t = await tab.evaluate(el => el.textContent.trim());
      if (t.includes(text)) { await tab.click(); return t; }
    }
    return null;
  }

  // Navigate to CPO Dashboard > Polygon Optimizer
  console.log('=== NAVIGATING TO POLYGON OPTIMIZER ===');
  await clickTab('CPO Dashboard');
  await sleep(5000);
  await clickTab('Polygon Optimizer');
  await sleep(3000);

  // Screenshot current state
  await scrollMain(page, 0);
  await sleep(500);
  await shot(page, 'poly-01-before-run');

  // Find and scroll to the Run button
  await scrollToText(page, 'Run Spatial Polygon Analysis');
  await sleep(500);
  await shot(page, 'poly-02-run-button');

  // Click the Run Spatial Polygon Analysis button
  console.log('Clicking "Run Spatial Polygon Analysis" button...');
  const clicked = await page.evaluate(() => {
    for (const btn of document.querySelectorAll('button')) {
      if (btn.textContent.includes('Run Spatial Polygon Analysis')) {
        btn.click();
        return true;
      }
    }
    return false;
  });
  console.log(`  Button clicked: ${clicked}`);

  if (!clicked) {
    console.log('ERROR: Could not find the Run button!');
    await browser.close();
    process.exit(1);
  }

  // Wait for the spinner to appear (analysis is running)
  await sleep(3000);
  await shot(page, 'poly-03-running-spinner');

  // Now wait for analysis to complete — check every 15 seconds, up to 8 minutes
  console.log('Waiting for analysis to complete (up to 8 minutes)...');
  const startTime = Date.now();
  let completed = false;

  for (let i = 0; i < 32; i++) {
    await sleep(15000); // Wait 15 seconds between checks
    const elapsed = Math.round((Date.now() - startTime) / 1000);

    // Check if spinner is gone and results appeared
    const status = await page.evaluate(() => {
      const body = document.body.innerText;
      const hasSpinner = !!document.querySelector('[data-testid="stSpinner"]') ||
                         body.includes('Calculating distances') ||
                         body.includes('matching AWBs');
      const hasResults = body.includes('Hubs Analyzed') ||
                         body.includes('Monthly Saving') ||
                         body.includes('Annual Saving') ||
                         body.includes('Polygons Scanned');
      const hasError = body.includes('Error') || body.includes('error') || body.includes('Traceback');
      return { hasSpinner, hasResults, hasError };
    });

    console.log(`  [${elapsed}s] spinner=${status.hasSpinner} results=${status.hasResults} error=${status.hasError}`);

    if (status.hasResults) {
      console.log(`  Analysis completed in ${elapsed}s!`);
      completed = true;
      break;
    }

    if (status.hasError && !status.hasSpinner) {
      console.log(`  Analysis may have errored at ${elapsed}s.`);
      await shot(page, 'poly-04-error');
      completed = true;
      break;
    }

    // Take a progress screenshot every minute
    if (i > 0 && i % 4 === 0) {
      await shot(page, `poly-progress-${elapsed}s`);
    }
  }

  if (!completed) {
    console.log('  Timed out after 8 minutes.');
    await shot(page, 'poly-04-timeout');
    await browser.close();
    process.exit(1);
  }

  // Screenshot the results
  await sleep(2000);
  await scrollMain(page, 0);
  await sleep(500);
  await shot(page, 'poly-05-results-top');

  // Scroll to metrics
  await scrollToText(page, 'Hubs Analyzed');
  await sleep(500);
  await shot(page, 'poly-06-results-metrics');

  // Scroll to see savings metrics
  await scrollToText(page, 'Monthly Saving');
  await sleep(500);
  await shot(page, 'poly-07-savings-metrics');

  // Scroll to SOP/spatial metrics
  await scrollToText(page, 'Polygons Scanned');
  await sleep(500);
  await shot(page, 'poly-08-spatial-metrics');

  // Scroll to suggestions table
  await scrollToText(page, 'Hub-by-Hub');
  await sleep(500);
  await shot(page, 'poly-09-suggestions-table');

  // Scroll to Before/After
  await scrollToText(page, 'Before / After');
  await sleep(500);
  await shot(page, 'poly-10-before-after');

  // Scroll further to see more comparisons
  await scrollMain(page, 99999);
  await sleep(500);
  await shot(page, 'poly-11-download-btn');

  // Extract key metrics from the page
  const metrics = await page.evaluate(() => {
    const body = document.body.innerText;
    const extract = (label) => {
      const lines = body.split('\n');
      for (let i = 0; i < lines.length; i++) {
        if (lines[i].includes(label) && i + 1 < lines.length) {
          return lines[i + 1].trim();
        }
      }
      return null;
    };
    return {
      hubsAnalyzed: extract('Hubs Analyzed'),
      hubsToOptimize: extract('Hubs to Optimize'),
      monthlySaving: extract('Monthly Saving'),
      annualSaving: extract('Annual Saving'),
      polygonsScanned: extract('Polygons Scanned'),
      sopCompliance: extract('SOP Compliance'),
      overchargedPolygons: extract('Overcharged Polygons'),
      monthlyBurn: extract('Monthly Burn'),
    };
  });

  console.log('\n=== POLYGON ANALYSIS RESULTS ===');
  for (const [key, val] of Object.entries(metrics)) {
    if (val) console.log(`  ${key}: ${val}`);
  }

  console.log('\n=== POLYGON ANALYSIS COMPLETE ===');
  await browser.close();
})();
