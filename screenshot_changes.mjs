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
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1920,1200']
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1920, height: 1200 });

  console.log('Loading app...');
  await page.goto('http://localhost:8501', { waitUntil: 'networkidle2', timeout: 60000 });
  await sleep(6000);

  // Step 1: Load existing files first so Step 3 works
  console.log('Loading existing data files...');

  // Click "Load final_output" button
  let loadResult = await page.evaluate(() => {
    const buttons = document.querySelectorAll('button');
    const clicked = [];
    for (const btn of buttons) {
      const txt = btn.textContent.trim();
      if (txt.includes('Load final_output') || txt.includes('Load polygons') || txt.includes('Load AWB raw') || txt.includes('Load AWB cluster')) {
        btn.click();
        clicked.push(txt);
      }
    }
    return clicked.length > 0 ? clicked.join(', ') : 'no load buttons found';
  });
  console.log('Load buttons clicked:', loadResult);
  await sleep(4000);

  // Upload the Clustering Automation CSV via file input
  const csvPath = join(process.cwd(), 'clustering_app (1)', 'clustering_app', 'data', 'Clustering_Automation.csv');
  console.log('Uploading cluster CSV:', csvPath);

  // Find the cluster CSV upload input
  const fileInputs = await page.$$('input[type="file"]');
  console.log('Found', fileInputs.length, 'file inputs');
  if (fileInputs.length >= 1 && existsSync(csvPath)) {
    await fileInputs[0].uploadFile(csvPath);
    console.log('Uploaded Clustering_Automation.csv');
    await sleep(5000);
  }

  // Screenshot after loading data
  let fp = nextFile('step1-data-loaded');
  await page.screenshot({ path: fp, fullPage: false });
  console.log('Data loaded:', fp);

  // Navigate to Step 3
  console.log('Navigating to Step 3...');
  const navResult = await page.evaluate(() => {
    const labels = document.querySelectorAll('[data-testid="stSidebar"] [role="radiogroup"] label');
    for (const label of labels) {
      if (label.textContent.includes('Polygon')) {
        label.click();
        return 'clicked: ' + label.textContent.trim();
      }
    }
    return 'not found';
  });
  console.log('Nav:', navResult);
  await sleep(6000);

  // Screenshot Step 3 overview
  fp = nextFile('step3-with-data');
  await page.screenshot({ path: fp, fullPage: false });
  console.log('Step 3 with data:', fp);

  // Scroll to find the "Polygon Generation" section with the number input
  await page.evaluate(() => {
    const elements = document.querySelectorAll('p, span, div, label');
    for (const el of elements) {
      if (el.textContent.includes('Default Distance Band') || el.textContent.includes('Distance Band Width')) {
        el.scrollIntoView({ behavior: 'instant', block: 'center' });
        return;
      }
    }
  });
  await sleep(2000);

  // Screenshot showing the distance band number input
  fp = nextFile('step3-distance-input');
  await page.screenshot({ path: fp, fullPage: false });
  console.log('Distance input:', fp);

  // Try clicking "Polygon Generation" expander if it's collapsed
  await page.evaluate(() => {
    const summaries = document.querySelectorAll('[data-testid="stExpanderToggle"], summary, [data-testid="stExpander"] > div:first-child');
    for (const s of summaries) {
      if (s.textContent.includes('Polygon Generation')) {
        s.click();
        return;
      }
    }
  });
  await sleep(3000);

  // Screenshot again after expanding
  fp = nextFile('step3-polygon-gen-expanded');
  await page.screenshot({ path: fp, fullPage: false });
  console.log('Polygon Gen expanded:', fp);

  // Try to expand Per-Hub Radius
  await page.evaluate(() => {
    const summaries = document.querySelectorAll('[data-testid="stExpanderToggle"], summary, [data-testid="stExpander"] > div:first-child');
    for (const s of summaries) {
      if (s.textContent.includes('Per-Hub') || s.textContent.includes('per-hub') || s.textContent.includes('Radius')) {
        s.click();
        return;
      }
    }
  });
  await sleep(3000);

  // Screenshot showing per-hub radius table
  fp = nextFile('step3-per-hub-radius');
  await page.screenshot({ path: fp, fullPage: false });
  console.log('Per-Hub Radius:', fp);

  // Full page Step 3 screenshot
  fp = nextFile('step3-full');
  await page.screenshot({ path: fp, fullPage: true });
  console.log('Full page:', fp);

  // Also screenshot the sidebar showing the Clear Cache button
  await page.evaluate(() => {
    const sidebar = document.querySelector('[data-testid="stSidebar"]');
    if (sidebar) sidebar.scrollTop = sidebar.scrollHeight;
  });
  await sleep(1000);
  fp = nextFile('sidebar-cache-btn');
  await page.screenshot({ path: fp, fullPage: false });
  console.log('Sidebar cache:', fp);

  await browser.close();
  console.log('Done!');
})();
