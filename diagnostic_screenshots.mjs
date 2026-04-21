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

// Scroll to text in Streamlit's main scrollable container
async function scrollToText(page, text) {
  return page.evaluate((searchText) => {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      if (walker.currentNode.textContent.includes(searchText)) {
        const el = walker.currentNode.parentElement;
        // Find the stMain scrollable parent
        let parent = el;
        while (parent) {
          const testId = parent.getAttribute('data-testid') || '';
          if (testId === 'stMain') {
            const rect = el.getBoundingClientRect();
            const parentRect = parent.getBoundingClientRect();
            parent.scrollTop += (rect.top - parentRect.top - 80);
            return true;
          }
          const style = window.getComputedStyle(parent);
          if (parent.scrollHeight > parent.clientHeight + 100 &&
              (style.overflowY === 'auto' || style.overflowY === 'scroll') &&
              parent.tagName !== 'HTML' && parent.tagName !== 'BODY') {
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

  // Helper to click any tab by text (native click)
  async function clickTab(text) {
    const tabs = await page.$$('[role="tab"]');
    for (const tab of tabs) {
      const t = await tab.evaluate(el => el.textContent.trim());
      if (t.includes(text)) { await tab.click(); return t; }
    }
    return null;
  }

  // ─── 1. GANDALF AI TAB (the one we just fixed) ───
  console.log('=== 1. GANDALF AI TAB ===');
  await clickTab('GANDALF');
  await sleep(8000);
  await scrollMain(page, 0);
  await sleep(500);
  await shot(page, 'FINAL-01-gandalf-top');

  // Scroll to see alerts/actions
  await scrollMain(page, 400);
  await sleep(500);
  await shot(page, 'FINAL-02-gandalf-alerts');

  // Scroll to chat
  await scrollToText(page, 'Ask GANDALF');
  await sleep(500);
  await shot(page, 'FINAL-03-gandalf-chat');

  // Scroll to quick actions
  await scrollToText(page, 'Quick Actions');
  await sleep(500);
  await shot(page, 'FINAL-04-gandalf-quick-actions');

  // Verify buttons
  const qaButtons = await page.evaluate(() => {
    return [...document.querySelectorAll('button')]
      .map(b => b.textContent.trim())
      .filter(t => ['Expensive', 'Merge', 'Reduce', 'Diagnostics', 'High Burn', 'Optimize',
                     'Save 20L', 'SOP', 'Exception', 'Custom'].some(kw => t.includes(kw)));
  });
  console.log(`  Quick action buttons: ${qaButtons.join(' | ')}`);

  // ─── 2. CPO DASHBOARD > POLYGON OPTIMIZER ───
  console.log('\n=== 2. POLYGON OPTIMIZER ===');
  await clickTab('CPO Dashboard');
  await sleep(5000);
  await clickTab('Polygon Optimizer');
  await sleep(3000);
  await scrollToText(page, 'Spatial polygon analysis');
  await sleep(500);
  await shot(page, 'FINAL-05-polygon-optimizer');

  await scrollToText(page, 'Run Spatial Polygon Analysis');
  await sleep(500);
  await shot(page, 'FINAL-06-polygon-run-btn');

  // ─── 3. CPO DASHBOARD > HIGH BURN HUBS ───
  console.log('\n=== 3. HIGH BURN HUBS ===');
  await clickTab('High Burn');
  await sleep(3000);
  await scrollToText(page, 'CPO Threshold');
  await sleep(500);
  await shot(page, 'FINAL-07-high-burn-threshold');

  await scrollToText(page, 'Download High Burn');
  await sleep(500);
  await shot(page, 'FINAL-08-high-burn-table');

  // ─── 4. MAPS STUDIO ───
  console.log('\n=== 4. MAPS STUDIO ===');
  await clickTab('Maps Studio');
  await sleep(10000);
  await shot(page, 'FINAL-09-maps-studio');

  // ─── 5. RECOMMENDATIONS ───
  console.log('\n=== 5. RECOMMENDATIONS ===');
  await clickTab('Recommendation');
  await sleep(5000);
  await shot(page, 'FINAL-10-recommendations');

  // ─── 6. MAP TAB ───
  console.log('\n=== 6. MAP TAB ===');
  await clickTab('Map');
  await sleep(3000);
  await shot(page, 'FINAL-11-map');

  console.log('\n=== ALL FINAL SCREENSHOTS CAPTURED ===');
  await browser.close();
})();
