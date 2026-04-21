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
  await sleep(5000);

  // Check for any error banners
  const errors = await page.evaluate(() => {
    const errEls = document.querySelectorAll('[data-testid="stException"], .stAlert, [data-testid="stNotification"]');
    return Array.from(errEls).map(e => e.textContent.substring(0, 200));
  });
  if (errors.length > 0) console.log('ERRORS FOUND:', errors);
  else console.log('No errors on page');

  // Load existing data
  let loadResult = await page.evaluate(() => {
    const btns = document.querySelectorAll('button');
    const clicked = [];
    for (const btn of btns) {
      const txt = btn.textContent.trim();
      if (txt.includes('Load final_output') || txt.includes('Load polygons') || txt.includes('Load AWB raw') || txt.includes('Load AWB cluster')) {
        btn.click(); clicked.push(txt);
      }
    }
    return clicked;
  });
  console.log('Loaded:', loadResult.join(', ') || 'none');
  await sleep(3000);

  // Upload CSV
  const csvPath = join(process.cwd(), 'clustering_app (1)', 'clustering_app', 'data', 'Clustering_Automation.csv');
  const fileInputs = await page.$$('input[type="file"]');
  if (fileInputs.length >= 1 && existsSync(csvPath)) {
    await fileInputs[0].uploadFile(csvPath);
    console.log('Uploaded CSV');
    await sleep(4000);
  }

  // Screenshot Step 1
  let fp = nextFile('verify-step1');
  await page.screenshot({ path: fp, fullPage: false });
  console.log('Step 1:', fp);

  // Check errors after data load
  const errorsAfter = await page.evaluate(() => {
    const errEls = document.querySelectorAll('[data-testid="stException"]');
    return Array.from(errEls).map(e => e.textContent.substring(0, 300));
  });
  if (errorsAfter.length > 0) console.log('ERRORS after load:', errorsAfter);

  // Navigate to each step and screenshot
  const steps = ['P Mapping', 'Polygon', 'AWB', 'Live Clusters', 'Financial', 'AI Agent'];
  for (const step of steps) {
    await page.evaluate((s) => {
      const labels = document.querySelectorAll('[data-testid="stSidebar"] [role="radiogroup"] label');
      for (const label of labels) {
        if (label.textContent.includes(s)) { label.click(); return; }
      }
    }, step);
    await sleep(4000);

    // Check for exceptions
    const stepErrors = await page.evaluate(() => {
      const errEls = document.querySelectorAll('[data-testid="stException"]');
      return Array.from(errEls).map(e => e.textContent.substring(0, 200));
    });

    const stepName = step.replace(/\s+/g, '-').toLowerCase();
    fp = nextFile(`verify-${stepName}`);
    await page.screenshot({ path: fp, fullPage: false });
    console.log(`${step}: ${fp}${stepErrors.length > 0 ? ' [HAS ERRORS]' : ' [OK]'}`);
    if (stepErrors.length > 0) console.log('  Errors:', stepErrors[0]);
  }

  await browser.close();
  console.log('Verification complete!');
})();
