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

  // Click Data tab
  await page.evaluate(() => {
    for (const tab of document.querySelectorAll('[role="tab"]'))
      if (tab.textContent.trim() === 'Data') { tab.click(); return; }
  });
  await sleep(5000);

  // Click AWB Data sub-tab
  console.log('Looking for AWB Data sub-tab...');
  const awbTabClicked = await page.evaluate(() => {
    for (const tab of document.querySelectorAll('[role="tab"]')) {
      if (tab.textContent.trim() === 'AWB Data') { tab.click(); return true; }
    }
    return false;
  });
  console.log('AWB tab clicked:', awbTabClicked);
  await sleep(3000);

  let fp = nextFile('awb-tab');
  await page.screenshot({ path: fp, fullPage: false });
  console.log('AWB tab:', fp);

  // Scroll to the BigQuery Fetch section (find "BigQuery Fetch" text)
  await page.evaluate(() => {
    const elements = document.querySelectorAll('h5, h4, h3, p, span');
    for (const el of elements) {
      if (el.textContent.includes('BigQuery Fetch') || el.textContent.includes('pincodes will be queried')) {
        el.scrollIntoView({ behavior: 'instant', block: 'center' });
        return;
      }
    }
    // fallback: scroll to bottom of main content
    const blocks = document.querySelectorAll('[data-testid="stVerticalBlockBorderWrapper"]');
    if (blocks.length > 0) blocks[blocks.length - 1].scrollIntoView({ block: 'center' });
  });
  await sleep(2000);

  fp = nextFile('bq-fetch-section');
  await page.screenshot({ path: fp, fullPage: false });
  console.log('BQ fetch section:', fp);

  // Find and expand the pincode preview
  const expandResult = await page.evaluate(() => {
    // Find all elements that could be expander headers
    const all = document.querySelectorAll('summary, [data-testid="stExpanderToggle"], [role="button"]');
    for (const el of all) {
      if (el.textContent.includes('pincodes') && el.textContent.includes('queried')) {
        el.click();
        return 'clicked: ' + el.textContent.substring(0, 80);
      }
    }
    // Try finding the expander wrapper
    const details = document.querySelectorAll('details');
    for (const d of details) {
      if (d.textContent.includes('pincodes')) {
        d.open = true;
        const sum = d.querySelector('summary');
        if (sum) sum.click();
        return 'details opened: ' + d.textContent.substring(0, 80);
      }
    }
    return 'not found';
  });
  console.log('Expand result:', expandResult);
  await sleep(2000);

  // Scroll to make sure expanded content is visible
  await page.evaluate(() => {
    const codeBlocks = document.querySelectorAll('code, pre, [data-testid="stCode"]');
    for (const el of codeBlocks) {
      if (el.textContent.length > 100 && el.textContent.includes(',')) {
        el.scrollIntoView({ behavior: 'instant', block: 'center' });
        return;
      }
    }
  });
  await sleep(1000);

  fp = nextFile('pincode-list-expanded');
  await page.screenshot({ path: fp, fullPage: false });
  console.log('Pincode list expanded:', fp);

  await browser.close();
  console.log('Done!');
})();
