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

  // Screenshot 1: Check sidebar for AWB upload section
  let fp = join(dir, getFilename('sidebar-overview'));
  await page.screenshot({ path: fp, fullPage: false });
  console.log(`Screenshot: ${fp}`);

  // Scroll sidebar down to find upload section
  await page.evaluate(() => {
    const sidebar = document.querySelector('[data-testid="stSidebar"]');
    if (sidebar) sidebar.scrollTop = sidebar.scrollHeight;
  });
  await sleep(1000);

  fp = join(dir, getFilename('sidebar-scrolled'));
  await page.screenshot({ path: fp, fullPage: false });
  console.log(`Screenshot: ${fp}`);

  // Navigate to Data tab (tab 4)
  await page.evaluate(() => {
    const tabs = document.querySelectorAll('[role="tab"]');
    for (const tab of tabs) {
      if (tab.textContent.includes('Data')) { tab.click(); return; }
    }
  });
  await sleep(5000);

  fp = join(dir, getFilename('data-tab'));
  await page.screenshot({ path: fp, fullPage: false });
  console.log(`Screenshot: ${fp}`);

  // Look for AWB Data subtab or section
  await page.evaluate(() => {
    const tabs = document.querySelectorAll('[role="tab"]');
    for (const tab of tabs) {
      if (tab.textContent.includes('AWB')) { tab.click(); return; }
    }
  });
  await sleep(3000);

  fp = join(dir, getFilename('awb-data-tab'));
  await page.screenshot({ path: fp, fullPage: false });
  console.log(`Screenshot: ${fp}`);

  // Scroll down to see full AWB upload section
  await page.evaluate(() => {
    window.scrollBy(0, 500);
  });
  await sleep(1000);

  fp = join(dir, getFilename('awb-data-scrolled'));
  await page.screenshot({ path: fp, fullPage: false });
  console.log(`Screenshot: ${fp}`);

  await browser.close();
})();
