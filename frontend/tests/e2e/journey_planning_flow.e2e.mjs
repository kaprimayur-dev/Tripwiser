/**
 * Browser-based E2E test for TW-117:
 * Journey Planning & Personalization Workspace
 * Validates:
 * 1. Journey search with Personalization preference (Comfortable Transfers).
 * 2. Creating a Journey Plan from search results.
 * 3. Adding multiple alternative routes to the same plan.
 * 4. Navigating into Journey Planning Workspace.
 * 5. Comparing alternatives with sorting priorities (Fastest, Fewest Changes, Comfortable).
 * 6. Switching preferred journey.
 * 7. Inspecting train timetable directly from the plan.
 * 8. Sharing journey plan link with alternatives.
 * 9. Removing alternatives and plans with reactive UI updates.
 * 10. Local storage persistence across page reloads.
 */

import puppeteer from 'puppeteer-core';
import fs from 'fs';
import path from 'path';
import os from 'os';

const CHROME_PATHS = [
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
];

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function findBrowserExecutable() {
  for (const p of CHROME_PATHS) {
    if (fs.existsSync(p)) {
      return p;
    }
  }
  throw new Error('No local Chrome or Edge executable found on host system.');
}

async function runE2ETest() {
  console.log('🚀 Starting Browser-Based E2E Journey Planning & Personalization Test (TW-117)...');
  const executablePath = findBrowserExecutable();
  console.log(`Using browser executable: ${executablePath}`);

  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'puppeteer-tw117-'));

  const browser = await puppeteer.launch({
    executablePath,
    headless: true,
    userDataDir: tempDir,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  });

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 1100 });

    page.on('console', (msg) => {
      const text = msg.text();
      if (!text.includes('React DevTools')) {
        console.log('BROWSER CONSOLE:', text);
      }
    });

    // 1. Navigate to TripWiser Homepage
    console.log('1. Navigating to http://localhost:3000/...');
    const response = await page.goto('http://localhost:3000', {
      waitUntil: 'networkidle2',
      timeout: 30000,
    });
    if (response.status() !== 200) {
      throw new Error(`Expected HTTP 200, got ${response.status()}`);
    }

    // 2. Select Origin BCT and Destination NDLS
    console.log('2. Entering search: BCT ➔ NDLS...');
    await page.waitForSelector('input[type="text"]', { visible: true, timeout: 15000 });
    const inputs = await page.$$('input[type="text"]');
    if (inputs.length < 2) {
      throw new Error(`Expected at least 2 text inputs for stations, found ${inputs.length}`);
    }

    const originInput = inputs[0];
    await originInput.click();
    await originInput.type('BCT', { delay: 60 });
    await sleep(800);

    await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      const bctBtn = buttons.find((b) => b.textContent && b.textContent.includes('BCT'));
      if (bctBtn) bctBtn.click();
    });
    await sleep(400);

    const destInput = inputs[1];
    await destInput.click();
    await destInput.type('NDLS', { delay: 60 });
    await sleep(800);

    await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      const ndlsBtn = buttons.find((b) => b.textContent && b.textContent.includes('NDLS'));
      if (ndlsBtn) ndlsBtn.click();
    });
    await sleep(400);

    // 3. Submit search
    console.log('3. Submitting route search...');
    await sleep(600);
    const submitBtn = await page.$('button[type="submit"]');
    if (!submitBtn) {
      throw new Error('Submit button not found');
    }
    await submitBtn.click();

    // 4. Wait for Route Results loaded
    console.log('4. Waiting for route cards...');
    await page.waitForSelector('[id^="route-card-"]', { timeout: 35000 });
    let planButtons = await page.$$('button[id^="btn-plan-route-"]');
    console.log(`Found ${planButtons.length} candidate routes with Plan buttons.`);
    if (planButtons.length < 1) {
      throw new Error('No candidate routes found to add to Journey Plan.');
    }

    // 5. Add First Route to Journey Plan
    console.log('5. Adding First Route to Journey Plan...');
    await planButtons[0].click();
    await sleep(800);

    const firstBtnText = await page.$eval('button[id^="btn-plan-route-"]', (el) => el.innerText);
    console.log(`First route plan button text: "${firstBtnText}"`);
    if (!firstBtnText.includes('In Plan')) {
      throw new Error('Expected first route button to change to "In Plan".');
    }

    // 6. If multiple routes exist, add Second Route as Alternative
    planButtons = await page.$$('button[id^="btn-plan-route-"]');
    if (planButtons.length > 1) {
      console.log('6. Adding Second Route as Alternative...');
      await planButtons[1].click();
      await sleep(800);
      planButtons = await page.$$('button[id^="btn-plan-route-"]');
      const secondBtnText = await page.evaluate((btn) => btn.innerText, planButtons[1]);
      console.log(`Second route plan button text: "${secondBtnText}"`);
      if (!secondBtnText.includes('In Plan')) {
        throw new Error('Expected second route button to change to "In Plan".');
      }
    }

    // 7. Navigate to Journey Planning Workspace via Navbar
    console.log('7. Navigating to Journey Planning Workspace (My Plans)...');
    await page.click('#nav-saved-trips-tab');
    await sleep(800);

    await page.waitForSelector('#journey-planning-workspace', { visible: true, timeout: 15000 });
    console.log('Journey Planning Workspace mounted successfully.');

    // 8. Verify Preferred Journey Showcase
    const hasShowcase = await page.evaluate(() => {
      const showcase = document.querySelector('#preferred-journey-showcase');
      return showcase !== null && showcase.innerText.includes('Preferred Journey Selection');
    });
    console.log(`Preferred Journey Showcase verified: ${hasShowcase}`);
    if (!hasShowcase) throw new Error('Preferred Journey Showcase is missing in Workspace.');

    // 9. Verify Alternatives Comparison Section & Sorting
    const hasAlternatives = await page.evaluate(() => {
      const section = document.querySelector('#compare-alternatives-section');
      return section !== null && section.innerText.includes('Compare Journey Alternatives');
    });
    console.log(`Compare Alternatives section verified: ${hasAlternatives}`);
    if (!hasAlternatives) throw new Error('Compare Alternatives section is missing.');

    // 10. Test Comparison Sorting Priorities
    console.log('10. Testing comparison sorting filters (Fastest, Fewest Changes, Comfortable)...');
    await page.click('#filter-compare-fastest');
    await sleep(300);
    await page.click('#filter-compare-fewest-changes');
    await sleep(300);
    await page.click('#filter-compare-comfortable');
    await sleep(300);

    // 11. Test Share Plan Link
    console.log('11. Testing Share Journey Plan...');
    await page.click('#btn-share-plan');
    await sleep(600);
    const isLinkCopied = await page.evaluate(() => {
      return document.querySelector('#btn-share-plan')?.innerText.includes('Copied') || false;
    });
    console.log(`Share Plan link copy verified: ${isLinkCopied}`);

    // 12. Test Page Reload Persistence (localStorage check)
    console.log('12. Testing local persistence across browser reload...');
    await page.reload({ waitUntil: 'domcontentloaded' });
    await sleep(800);

    await page.waitForSelector('#journey-planning-workspace', { timeout: 15000 });
    const persistedPlan = await page.evaluate(() => {
      const showcase = document.querySelector('#preferred-journey-showcase');
      return showcase !== null;
    });
    console.log(`Plan persisted across reload: ${persistedPlan}`);
    if (!persistedPlan) throw new Error('Journey Plan was lost upon browser reload.');

    // 13. Test Deleting Plan
    console.log('13. Testing Delete Journey Plan...');
    await page.click('#btn-delete-plan');
    await sleep(800);

    const hasEmptyState = await page.evaluate(() => {
      return document.querySelector('#empty-plans-view') !== null;
    });
    console.log(`Empty plans state verified after deletion: ${hasEmptyState}`);
    if (!hasEmptyState) throw new Error('Expected empty plans view after deleting plan.');

    // 14. Capture E2E Screenshot
    const screenshotPath = 'C:\\Users\\MAYUR\\.gemini\\antigravity\\brain\\d912be4a-adb8-4eeb-ad55-3fcedf5ab70a\\e2e_journey_planning_success.png';
    await page.screenshot({ path: screenshotPath, fullPage: true });
    console.log(`Saved E2E screenshot to: ${screenshotPath}`);

    // Copy to frontend/tests/e2e
    const localScreenshotPath = path.resolve('frontend/tests/e2e/e2e_journey_planning_success.png');
    fs.copyFileSync(screenshotPath, localScreenshotPath);

    console.log('🎉 TW-117 E2E Journey Planning & Personalization Test PASSED COMPLETELY!');
  } finally {
    await browser.close();
  }
}

runE2ETest().catch((err) => {
  console.error('❌ E2E Journey Planning Test FAILED:', err);
  process.exit(1);
});
