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

  // Load data
  await page.evaluate(() => {
    for (const btn of document.querySelectorAll('button')) {
      const t = btn.textContent.trim();
      if (t.includes('Load final_output') || t.includes('Load polygons') || t.includes('Load AWB raw') || t.includes('Load AWB cluster'))
        btn.click();
    }
  });
  await sleep(3000);

  const csvPath = join(process.cwd(), 'clustering_app (1)', 'clustering_app', 'data', 'Clustering_Automation.csv');
  const fileInputs = await page.$$('input[type="file"]');
  if (fileInputs.length >= 1 && existsSync(csvPath)) {
    await fileInputs[0].uploadFile(csvPath);
    await sleep(4000);
  }

  // ── LIGHT MODE screenshot ──
  let fp = nextFile('LIGHT-step1');
  await page.screenshot({ path: fp, fullPage: false });
  console.log('Light Step 1:', fp);

  // ── Click Dark Mode toggle ──
  console.log('Clicking Dark Mode toggle...');
  const toggleClicked = await page.evaluate(() => {
    // Find the toggle by looking for the label text
    const labels = document.querySelectorAll('[data-testid="stSidebar"] label');
    for (const label of labels) {
      if (label.textContent.includes('Dark Mode')) {
        // Click the toggle input inside the label
        const toggle = label.querySelector('input[type="checkbox"], [role="checkbox"]');
        if (toggle) { toggle.click(); return 'clicked checkbox'; }
        // Fallback: click the label itself
        label.click();
        return 'clicked label: ' + label.textContent.trim();
      }
    }
    // Try finding toggle by data-testid
    const toggles = document.querySelectorAll('[data-testid="stToggle"]');
    for (const t of toggles) {
      if (t.textContent.includes('Dark')) {
        const input = t.querySelector('input, [role="checkbox"]');
        if (input) { input.click(); return 'clicked toggle input'; }
        t.click();
        return 'clicked toggle container';
      }
    }
    return 'toggle not found';
  });
  console.log('Toggle result:', toggleClicked);
  await sleep(5000);

  // ── DARK MODE screenshot ──
  fp = nextFile('DARK-step1');
  await page.screenshot({ path: fp, fullPage: false });
  console.log('Dark Step 1:', fp);

  // Navigate to Step 3 in dark mode
  await page.evaluate(() => {
    const labels = document.querySelectorAll('[data-testid="stSidebar"] [role="radiogroup"] label');
    for (const label of labels) {
      if (label.textContent.includes('Polygon')) { label.click(); return; }
    }
  });
  await sleep(5000);

  fp = nextFile('DARK-step3');
  await page.screenshot({ path: fp, fullPage: false });
  console.log('Dark Step 3:', fp);

  // Navigate to Financial Intel in dark mode
  await page.evaluate(() => {
    const labels = document.querySelectorAll('[data-testid="stSidebar"] [role="radiogroup"] label');
    for (const label of labels) {
      if (label.textContent.includes('Financial')) { label.click(); return; }
    }
  });
  await sleep(5000);

  fp = nextFile('DARK-step6');
  await page.screenshot({ path: fp, fullPage: false });
  console.log('Dark Step 6:', fp);

  await browser.close();
  console.log('Done!');
})();
