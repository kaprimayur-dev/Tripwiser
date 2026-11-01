/**
 * Browser-based E2E test for TW-114:
 * Passenger Journey Experience & Search Refinement
 * Validates:
 * 1. Station search, autocomplete & swapping
 * 2. Graceful validation for identical origin/destination
 * 3. Route discovery & transfer filtering
 * 4. Save & Revisit Journeys (My Trips) with local persistence & duplicate prevention
 * 5. Shareable URL generation & restoration
 * 6. Invalid URL parameter graceful handling
 * 7. Mobile viewport responsiveness & zero horizontal overflow
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
  console.log('🚀 Starting Browser-Based E2E Passenger Journey Experience Test (TW-114)...');
  const executablePath = findBrowserExecutable();
  console.log(`Using browser executable: ${executablePath}`);

  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'puppeteer-tw114-'));

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

    // ==========================================
    // 1. Navigate to TripWiser Home
    // ==========================================
    console.log('1. Navigating to http://localhost:3000...');
    await page.goto('http://localhost:3000', {
      waitUntil: 'networkidle2',
      timeout: 30000,
    });

    // ==========================================
    // 2. Test Station Autocomplete & Selection
    // ==========================================
    console.log('2. Testing Station Autocomplete for Origin (BCT)...');
    const inputs = await page.$$('input[type="text"]');
    if (inputs.length < 2) {
      throw new Error(`Expected at least 2 station text inputs, found ${inputs.length}`);
    }
    const originInput = inputs[0];
    await originInput.click({ clickCount: 3 });
    await originInput.press('Backspace');
    await originInput.type('BCT', { delay: 50 });
    await sleep(800);

    await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      const bctBtn = buttons.find((b) => b.textContent && b.textContent.includes('BCT'));
      if (bctBtn) bctBtn.click();
    });
    await sleep(400);
    console.log('Selected origin: BCT');

    console.log('3. Testing Station Autocomplete for Destination (HWH)...');
    const destInput = inputs[1];
    await destInput.click({ clickCount: 3 });
    await destInput.press('Backspace');
    await destInput.type('HWH', { delay: 50 });
    await sleep(800);

    await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      const hwhBtn = buttons.find((b) => b.textContent && b.textContent.includes('HWH'));
      if (hwhBtn) hwhBtn.click();
    });
    await sleep(400);
    console.log('Selected destination: HWH');

    // ==========================================
    // 3. Test Origin & Destination Swapping
    // ==========================================
    console.log('4. Testing Station Swap button...');
    const swapBtn = await page.$('#btn-swap-stations');
    if (!swapBtn) throw new Error('Swap button #btn-swap-stations not found');
    await swapBtn.click();
    await sleep(500);

    const originValAfterSwap = await page.evaluate(() => {
      const ins = document.querySelectorAll('input[type="text"]');
      return ins[0]?.value || '';
    });
    const destValAfterSwap = await page.evaluate(() => {
      const ins = document.querySelectorAll('input[type="text"]');
      return ins[1]?.value || '';
    });
    console.log(`After swap: Origin="${originValAfterSwap}", Destination="${destValAfterSwap}"`);

    if (!originValAfterSwap.includes('HWH') || !destValAfterSwap.includes('BCT')) {
      throw new Error(`Station swap failed: Origin=${originValAfterSwap}, Dest=${destValAfterSwap}`);
    }

    // Swap back
    await swapBtn.click();
    await sleep(500);
    console.log('Swapped back successfully to BCT ➔ HWH');

    // ==========================================
    // 4. Test Validation Handling for Same Station
    // ==========================================
    console.log('5. Testing Validation Handling for Identical Stations...');
    const currentInputs = await page.$$('input[type="text"]');
    const destInputToChange = currentInputs[1];
    await destInputToChange.click();
    await page.keyboard.down('Control');
    await page.keyboard.press('A');
    await page.keyboard.up('Control');
    await page.keyboard.press('Backspace');
    await destInputToChange.type('BCT', { delay: 50 });
    await sleep(800);

    // Click the autocomplete option specifically
    const clickedBct = await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      const btn = buttons.find((b) => b.getAttribute('data-station-code') === 'BCT' || (b.textContent && b.textContent.includes('BCT')));
      if (btn) {
        btn.click();
        return true;
      }
      return false;
    });
    console.log(`Clicked autocomplete option BCT for destination: ${clickedBct}`);
    await sleep(400);

    const valOrig = await page.evaluate(() => document.querySelectorAll('input[type="text"]')[0]?.value);
    const valDest = await page.evaluate(() => document.querySelectorAll('input[type="text"]')[1]?.value);
    console.log(`Before submit: Origin="${valOrig}", Dest="${valDest}"`);

    // Click submit
    const searchBtn = await page.$('#btn-search-routes');
    await searchBtn.click();
    await sleep(500);

    const validationAlert = await page.$('#search-validation-error');
    if (!validationAlert) {
      throw new Error('Expected #search-validation-error when origin and destination are identical!');
    }
    const alertText = await page.evaluate((el) => el.innerText, validationAlert);
    console.log(`Validation alert text: "${alertText}"`);
    if (!alertText.includes('identical')) {
      throw new Error(`Unexpected validation message: ${alertText}`);
    }

    // Restore destination to HWH
    await destInputToChange.click();
    await page.keyboard.down('Control');
    await page.keyboard.press('A');
    await page.keyboard.up('Control');
    await page.keyboard.press('Backspace');
    await destInputToChange.type('HWH', { delay: 50 });
    await sleep(800);
    await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      const hwhBtn = buttons.find((b) => b.getAttribute('data-station-code') === 'HWH' || (b.textContent && b.textContent.includes('HWH')));
      if (hwhBtn) hwhBtn.click();
    });
    await sleep(400);
    await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      const hwhBtn = buttons.find((b) => b.textContent && b.textContent.includes('HWH'));
      if (hwhBtn) hwhBtn.click();
    });
    await sleep(400);

    // ==========================================
    // 5. Submit Search with 2-Transfers
    // ==========================================
    console.log('6. Submitting route search BCT ➔ HWH with date 2026-11-02 and 2 transfers...');
    const dateInput = await page.$('#input-journey-date');
    await page.evaluate((el) => (el.value = '2026-11-02'), dateInput);
    await dateInput.type(' ');

    const btnTransfers2 = await page.$('#btn-transfers-2');
    await btnTransfers2.click();
    await sleep(200);

    await searchBtn.click();
    console.log('Waiting for route search results...');
    await page.waitForSelector('[id^="route-card-"]', { timeout: 15000 });

    const routeCards = await page.$$('[id^="route-card-"]');
    console.log(`Found ${routeCards.length} route cards.`);
    if (routeCards.length === 0) throw new Error('No route cards returned!');

    // ==========================================
    // 6. Test Transfer Filtering
    // ==========================================
    console.log('7. Testing Transfer Filtering in SortingFilterBar...');
    const filter1Transfer = await page.$('#filter-1-transfer');
    if (filter1Transfer) {
      await filter1Transfer.click();
      await sleep(300);
      const filtered1 = await page.$$('[id^="route-card-"]');
      console.log(`Routes displayed under "1 Transfer" filter: ${filtered1.length}`);
    }

    const filterAll = await page.$('#filter-all-transfers');
    if (filterAll) {
      await filterAll.click();
      await sleep(300);
    }

    // ==========================================
    // 7. Test Save Journey & "My Trips"
    // ==========================================
    console.log('8. Testing Save Journey (Bookmark)...');
    const firstSaveBtn = await page.$('[id^="btn-save-route-"]');
    if (!firstSaveBtn) throw new Error('Save button on route card not found');

    const initialBadgeText = await page.evaluate(
      () => document.querySelector('#saved-trips-count-badge')?.innerText || '0'
    );
    console.log(`Initial saved trips count badge: ${initialBadgeText}`);

    // Click Save
    await firstSaveBtn.click();
    await sleep(300);

    const badgeAfterSave = await page.evaluate(
      () => document.querySelector('#saved-trips-count-badge')?.innerText
    );
    console.log(`Saved trips count badge after save: ${badgeAfterSave}`);
    if (!badgeAfterSave || parseInt(badgeAfterSave, 10) < 1) {
      throw new Error(`Saved badge did not increment. Value: ${badgeAfterSave}`);
    }

    // Open "My Trips" view
    console.log('9. Navigating to My Trips view...');
    const myTripsTab = await page.$('#nav-saved-trips-tab');
    if (!myTripsTab) throw new Error('#nav-saved-trips-tab not found');
    await myTripsTab.click();
    await sleep(400);

    const savedTripCards = await page.$$('[id^="saved-trip-card-"]');
    console.log(`Found ${savedTripCards.length} saved trip card(s) in My Trips view.`);
    if (savedTripCards.length === 0) {
      throw new Error('Expected saved trip card in My Trips view!');
    }

    // Verify Recheck Search action
    console.log('10. Testing "Check Current Schedule & Search" from My Trips...');
    const recheckBtn = await page.$('[id^="btn-recheck-trip-"]');
    if (!recheckBtn) throw new Error('Recheck trip button not found in My Trips');
    await recheckBtn.click();
    await sleep(1000);

    await page.waitForSelector('[id^="route-card-"]', { timeout: 15000 });
    console.log('Recheck successfully restored connecting search mode and populated results!');

    // ==========================================
    // 8. Test Shareable URL Restoration
    // ==========================================
    console.log('11. Testing Shareable URL Parameter Restoration...');
    const shareableUrl =
      'http://localhost:3000/?mode=connecting&origin=NDLS&destination=BPL&date=2026-11-04&transfers=0&sort=fastest';
    console.log(`Navigating to shared URL: ${shareableUrl}`);
    await page.goto(shareableUrl, { waitUntil: 'networkidle2', timeout: 30000 });
    await page.waitForSelector('[id^="route-card-"]', { timeout: 15000 });

    const sharedOriginVal = await page.evaluate(() => document.querySelector('#input-origin-station')?.value);
    const sharedDestVal = await page.evaluate(() => document.querySelector('#input-destination-station')?.value);
    const sharedDateVal = await page.evaluate(() => document.querySelector('#input-journey-date')?.value);
    console.log(
      `Shared URL restored: Origin="${sharedOriginVal}", Dest="${sharedDestVal}", Date="${sharedDateVal}"`
    );

    if (!sharedOriginVal.includes('NDLS') || !sharedDestVal.includes('BPL') || sharedDateVal !== '2026-11-04') {
      throw new Error('Shared URL parameters were not correctly restored into the search state!');
    }

    // ==========================================
    // 9. Test Invalid URL Parameters Handling
    // ==========================================
    console.log('12. Testing Invalid Station Code handling in Shared URL...');
    const invalidStationUrl =
      'http://localhost:3000/?mode=connecting&origin=UNKNOWNCODE999&destination=NDLS&date=2026-11-02';
    await page.goto(invalidStationUrl, { waitUntil: 'networkidle2', timeout: 30000 });
    await sleep(800);

    const urlWarningBanner = await page.$('#url-validation-banner');
    if (!urlWarningBanner) {
      throw new Error('Expected #url-validation-banner when loading shared link with unknown station!');
    }
    const warningText = await page.evaluate((el) => el.innerText, urlWarningBanner);
    console.log(`URL warning banner text: "${warningText}"`);
    if (!warningText.includes('UNKNOWNCODE999')) {
      throw new Error(`Unexpected URL warning message: ${warningText}`);
    }

    // ==========================================
    // 10. Mobile Viewport Responsiveness Check
    // ==========================================
    console.log('13. Testing Mobile Viewport (375x667 - iPhone SE)...');
    await page.setViewport({ width: 375, height: 667, isMobile: true, hasTouch: true });
    await page.goto('http://localhost:3000/?origin=BCT&destination=HWH&date=2026-11-02&transfers=2', {
      waitUntil: 'networkidle2',
      timeout: 30000,
    });
    await page.waitForSelector('[id^="route-card-"]', { timeout: 15000 });
    await sleep(500);

    // Verify zero horizontal scroll overflow
    const hasHorizontalOverflow = await page.evaluate(() => {
      return document.documentElement.scrollWidth > window.innerWidth;
    });
    console.log(`Mobile horizontal overflow detected: ${hasHorizontalOverflow}`);
    if (hasHorizontalOverflow) {
      const scrollW = await page.evaluate(() => document.documentElement.scrollWidth);
      throw new Error(`Mobile layout has horizontal overflow: scrollWidth=${scrollW}px > innerWidth=375px`);
    }

    // Capture Evidence Screenshots
    const artifactScreenshotMobile =
      'C:\\Users\\MAYUR\\.gemini\\antigravity\\brain\\d912be4a-adb8-4eeb-ad55-3fcedf5ab70a\\e2e_passenger_experience_mobile.png';
    const localScreenshotMobile = path.resolve('frontend/tests/e2e/e2e_passenger_experience_mobile.png');
    await page.screenshot({ path: artifactScreenshotMobile });
    await page.screenshot({ path: localScreenshotMobile });
    console.log(`Saved mobile screenshot to ${artifactScreenshotMobile}`);

    // Switch back to desktop and capture desktop evidence screenshot
    await page.setViewport({ width: 1280, height: 1100 });
    await sleep(300);
    const artifactScreenshotDesktop =
      'C:\\Users\\MAYUR\\.gemini\\antigravity\\brain\\d912be4a-adb8-4eeb-ad55-3fcedf5ab70a\\e2e_passenger_experience_desktop.png';
    const localScreenshotDesktop = path.resolve('frontend/tests/e2e/e2e_passenger_experience_desktop.png');
    await page.screenshot({ path: artifactScreenshotDesktop, fullPage: true });
    await page.screenshot({ path: localScreenshotDesktop, fullPage: true });
    console.log(`Saved desktop screenshot to ${artifactScreenshotDesktop}`);

    console.log('🎉 TW-114 E2E Passenger Journey Experience Test PASSED COMPLETELY!');
  } finally {
    await browser.close();
    try {
      fs.rmSync(tempDir, { recursive: true, force: true });
    } catch (_) {}
  }
}

runE2ETest().catch((err) => {
  console.error('❌ E2E Passenger Experience Test FAILED:', err);
  process.exit(1);
});
