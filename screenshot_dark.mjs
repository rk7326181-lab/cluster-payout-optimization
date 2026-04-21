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

  // Enable dark color scheme BEFORE loading the app
  await page.emulateMediaFeatures([{ name: 'prefers-color-scheme', value: 'dark' }]);

  console.log('Loading app in DARK mode...');
  await page.goto('http://localhost:8501', { waitUntil: 'networkidle2', timeout: 60000 });
  await sleep(6000);

  // Step 1: Load existing data
  console.log('Loading existing data files...');
  await page.evaluate(() => {
    const buttons = document.querySelectorAll('button');
    for (const btn of buttons) {
      const txt = btn.textContent.trim();
      if (txt.includes('Load final_output') || txt.includes('Load polygons') || txt.includes('Load AWB raw') || txt.includes('Load AWB cluster')) {
        btn.click();
      }
    }
  });
  await sleep(4000);

  // Upload CSV
  const csvPath = join(process.cwd(), 'clustering_app (1)', 'clustering_app', 'data', 'Clustering_Automation.csv');
  const fileInputs = await page.$$('input[type="file"]');
  if (fileInputs.length >= 1 && existsSync(csvPath)) {
    await fileInputs[0].uploadFile(csvPath);
    await sleep(5000);
  }

  let fp = nextFile('dark-step1');
  await page.screenshot({ path: fp, fullPage: false });
  console.log('Dark Step 1:', fp);

  // Navigate to Step 3
  const navResult = await page.evaluate(() => {
    const labels = document.querySelectorAll('[data-testid="stSidebar"] [role="radiogroup"] label');
    for (const label of labels) {
      if (label.textContent.includes('Polygon')) { label.click(); return 'clicked'; }
    }
    return 'not found';
  });
  console.log('Nav:', navResult);
  await sleep(6000);

  fp = nextFile('dark-step3');
  await page.screenshot({ path: fp, fullPage: false });
  console.log('Dark Step 3:', fp);

  // Navigate to Step 2 (P Mapping)
  await page.evaluate(() => {
    const labels = document.querySelectorAll('[data-testid="stSidebar"] [role="radiogroup"] label');
    for (const label of labels) {
      if (label.textContent.includes('P Mapping')) { label.click(); return; }
    }
  });
  await sleep(5000);

  fp = nextFile('dark-step2');
  await page.screenshot({ path: fp, fullPage: false });
  console.log('Dark Step 2:', fp);

  await browser.close();
  console.log('Done!');
})();
