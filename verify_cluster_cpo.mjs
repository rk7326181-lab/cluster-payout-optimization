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

  // ─── CPO DASHBOARD ───
  console.log('=== CPO DASHBOARD - Cluster CPO Verification ===');
  await clickTab('CPO Dashboard');
  await sleep(5000);

  // Screenshot top KPIs
  await scrollMain(page, 0);
  await sleep(500);
  await shot(page, 'cluster-cpo-01-kpis');

  // Check for "Cluster CPO" text and absence of "Pn CPO" / "Net CPO"
  const textCheck = await page.evaluate(() => {
    const body = document.body.innerText;
    return {
      hasClusterCPO: body.includes('Cluster CPO'),
      hasPnCPO: body.includes('Pn CPO') || body.includes('Pn_CPO') || body.includes('Pin CPO'),
      hasNetCPO: body.includes('Net CPO') || body.includes('Net_CPO'),
      hasAvgClusterCPO: body.includes('Avg Cluster CPO'),
    };
  });
  console.log('  Text check:', JSON.stringify(textCheck));

  // Scroll to comparison table
  await scrollToText(page, 'Cluster Comparison');
  await sleep(500);
  await shot(page, 'cluster-cpo-02-comparison');

  // Scroll to distribution chart
  await scrollToText(page, 'Distribution');
  await sleep(500);
  await shot(page, 'cluster-cpo-03-distribution');

  // Click High Cluster CPO Hubs sub-tab
  await clickTab('High Cluster CPO');
  await sleep(3000);
  await scrollMain(page, 0);
  await sleep(500);
  await shot(page, 'cluster-cpo-04-high-cluster-cpo');

  // Scroll to see data table
  await scrollMain(page, 400);
  await sleep(500);
  await shot(page, 'cluster-cpo-05-high-cpo-table');

  // Check columns in any visible table
  const tableHeaders = await page.evaluate(() => {
    const headers = [];
    document.querySelectorAll('th, [data-testid="stDataFrameCell"]').forEach(el => {
      const txt = el.textContent.trim();
      if (txt && txt.length < 30) headers.push(txt);
    });
    return [...new Set(headers)].slice(0, 20);
  });
  console.log('  Visible table headers:', tableHeaders.join(', '));

  // Click High Burn Hubs sub-tab
  await clickTab('High Burn');
  await sleep(3000);
  await scrollMain(page, 0);
  await sleep(500);
  await shot(page, 'cluster-cpo-06-high-burn');

  // Click Polygon Optimizer sub-tab
  await clickTab('Polygon Optimizer');
  await sleep(3000);
  await scrollMain(page, 0);
  await sleep(500);
  await shot(page, 'cluster-cpo-07-polygon-optimizer');

  // ─── GANDALF AI TAB ───
  console.log('\n=== GANDALF AI TAB ===');
  await clickTab('GANDALF');
  await sleep(8000);
  await scrollMain(page, 0);
  await sleep(500);
  await shot(page, 'cluster-cpo-08-gandalf');

  // Scroll down for more GANDALF content
  await scrollMain(page, 500);
  await sleep(500);
  await shot(page, 'cluster-cpo-09-gandalf-actions');

  // Check GANDALF loaded (not blank)
  const gandalfContent = await page.evaluate(() => {
    const main = document.querySelector('[data-testid="stMain"]');
    return main ? main.innerText.substring(0, 500) : 'NO MAIN';
  });
  console.log('  GANDALF content preview:', gandalfContent.substring(0, 200));

  console.log('\n=== VERIFICATION COMPLETE ===');
  await browser.close();
})();
