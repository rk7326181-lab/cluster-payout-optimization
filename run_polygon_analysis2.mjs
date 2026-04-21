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

async function clickTab(page, text) {
  const tabs = await page.$$('[role="tab"]');
  for (const tab of tabs) {
    const t = await tab.evaluate(el => el.textContent.trim());
    if (t.includes(text)) { await tab.click(); return t; }
  }
  return null;
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

  // Navigate to CPO Dashboard > Polygon Optimizer
  console.log('=== STEP 1: Navigate to Polygon Optimizer ===');
  await clickTab(page, 'CPO Dashboard');
  await sleep(5000);

  // Scroll down to find sub-tabs and click Polygon Optimizer
  await scrollToText(page, 'Polygon Optimizer');
  await sleep(500);
  await clickTab(page, 'Polygon Optimizer');
  await sleep(3000);

  // Scroll down to the Run button area
  await scrollToText(page, 'Monthly Savings Target');
  await sleep(500);
  await shot(page, 'poly2-01-savings-target');

  await scrollToText(page, 'Run Spatial Polygon Analysis');
  await sleep(500);
  await shot(page, 'poly2-02-run-button-visible');

  // Click the Run Spatial Polygon Analysis button
  console.log('\n=== STEP 2: Click Run button ===');
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

  // Wait for spinner
  await sleep(2000);

  // Check for spinner
  const hasSpinner = await page.evaluate(() => {
    return document.body.innerText.includes('Calculating distances') ||
           !!document.querySelector('[data-testid="stSpinner"]');
  });
  console.log(`  Spinner visible: ${hasSpinner}`);
  await shot(page, 'poly2-03-spinner');

  // Wait for analysis to complete - poll every 10 seconds, up to 8 minutes
  console.log('\n=== STEP 3: Waiting for analysis (up to 8 min) ===');
  const startTime = Date.now();
  let completed = false;

  for (let i = 0; i < 48; i++) {
    await sleep(10000);
    const elapsed = Math.round((Date.now() - startTime) / 1000);

    const status = await page.evaluate(() => {
      const body = document.body.innerText;
      return {
        hasSpinner: body.includes('Calculating distances') || body.includes('matching AWBs'),
        hasHubsAnalyzed: body.includes('Hubs Analyzed'),
        hasMonthlyBurn: body.includes('Monthly Burn'),
        hasSuggestions: body.includes('Hub-by-Hub Spatial Optimization'),
        hasBeforeAfter: body.includes('Before / After'),
        hasDownload: body.includes('Download Spatial Optimization'),
      };
    });

    console.log(`  [${elapsed}s] spinner=${status.hasSpinner} analyzed=${status.hasHubsAnalyzed} burn=${status.hasMonthlyBurn} suggestions=${status.hasSuggestions} ba=${status.hasBeforeAfter}`);

    if (status.hasHubsAnalyzed || status.hasSuggestions || status.hasBeforeAfter || status.hasDownload) {
      console.log(`  COMPLETED in ${elapsed}s!`);
      completed = true;
      break;
    }
  }

  if (!completed) {
    console.log('  Timed out.');
    await shot(page, 'poly2-timeout');
    await browser.close();
    process.exit(1);
  }

  // After rerun, re-navigate to the sub-tab since Streamlit reruns
  console.log('\n=== STEP 4: Re-navigate to results ===');
  await sleep(2000);

  // Click Polygon Optimizer sub-tab again (Streamlit may have preserved it, but let's be safe)
  await clickTab(page, 'Polygon Optimizer');
  await sleep(3000);

  // Now scroll down past the top-level content to the sub-tab results
  // First scroll to the sub-tab area
  await scrollToText(page, 'Spatial polygon analysis');
  await sleep(500);
  await shot(page, 'poly2-04-subtab-top');

  // Scroll to the metrics (Hubs Analyzed, etc.)
  await scrollToText(page, 'Hubs Analyzed');
  await sleep(500);
  await shot(page, 'poly2-05-hubs-analyzed');

  // Scroll to see Polygons Scanned row
  await scrollToText(page, 'Polygons Scanned');
  await sleep(500);
  await shot(page, 'poly2-06-polygons-scanned');

  // Scroll to target progress bar
  await scrollToText(page, 'Target:');
  await sleep(500);
  await shot(page, 'poly2-07-target-progress');

  // Scroll to Hub-by-Hub table
  await scrollToText(page, 'Hub-by-Hub');
  await sleep(500);
  await shot(page, 'poly2-08-hub-table');

  // Scroll to Before/After
  const hasBA = await scrollToText(page, 'Before / After');
  await sleep(500);
  await shot(page, 'poly2-09-before-after');

  // Scroll to Download button
  await scrollToText(page, 'Download Spatial');
  await sleep(500);
  await shot(page, 'poly2-10-download');

  // Extract all visible metrics
  const metrics = await page.evaluate(() => {
    const body = document.body.innerText;
    // Find metric values by looking for number patterns near known labels
    const results = {};
    const patterns = [
      'Hubs Analyzed', 'Hubs to Optimize', 'Monthly Saving', 'Annual Saving',
      'Polygons Scanned', 'SOP Compliance', 'Overcharged Polygons', 'Monthly Burn',
      'Exception Rates', 'Custom Radii', 'Reviews Needed', 'Non-Standard'
    ];
    const lines = body.split('\n').map(l => l.trim()).filter(l => l);
    for (const pat of patterns) {
      for (let i = 0; i < lines.length; i++) {
        if (lines[i].includes(pat)) {
          // The value is often on the next line
          if (i + 1 < lines.length) {
            results[pat] = lines[i + 1];
          }
          break;
        }
      }
    }
    return results;
  });

  console.log('\n=== ANALYSIS RESULTS ===');
  for (const [key, val] of Object.entries(metrics)) {
    console.log(`  ${key}: ${val}`);
  }

  console.log('\n=== DONE ===');
  await browser.close();
})();
