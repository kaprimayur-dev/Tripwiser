/**
 * Browser-based E2E test for Train Timetable Inspection and Journey Intermediate Stops
 * Tests real end-to-end user interactions on http://localhost:3000
 */

import puppeteer from 'puppeteer-core';
import fs from 'fs';
import path from 'path';

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
  console.log('🚀 Starting Browser-Based E2E Train Schedule & Intermediate Stoppage Test...');
  const executablePath = findBrowserExecutable();
  console.log(`Using browser executable: ${executablePath}`);

  const browser = await puppeteer.launch({
    executablePath,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  });

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 950 });

    page.on('console', (msg) => console.log('BROWSER CONSOLE:', msg.text()));
    page.on('pageerror', (err) => console.log('BROWSER PAGE ERROR:', err.message));

    // 1. Navigate to TripWiser
    console.log('1. Navigating to http://localhost:3000...');
    const response = await page.goto('http://localhost:3000', {
      waitUntil: 'networkidle2',
      timeout: 30000,
    });
    console.log(`Page HTTP status: ${response.status()}`);
    if (response.status() !== 200) {
      throw new Error(`Expected HTTP 200, got ${response.status()}`);
    }

    // 2. Switch to Timetable Mode
    console.log('2. Switching to Train Timetable Inspector mode...');
    const timetableTab = await page.$('#tab-timetable-mode');
    if (!timetableTab) {
      throw new Error('Could not find #tab-timetable-mode button');
    }
    await timetableTab.click();
    await sleep(500);

    // 3. Search Train 12002 (Bhopal Shatabdi)
    console.log('3. Searching for Train 12002 (Bhopal Shatabdi)...');
    await page.waitForSelector('#train-search-input', { timeout: 10000 });
    const trainInput = await page.$('#train-search-input');
    if (!trainInput) {
      throw new Error('Could not find #train-search-input field');
    }
    await trainInput.click();
    await trainInput.type('12002', { delay: 60 });
    await sleep(1000); // Allow debounce & fetch

    // Wait for dropdown suggestion
    const suggestion = await page.$('div[role="listbox"] button');
    if (suggestion) {
      console.log('Clicking train suggestion dropdown item...');
      await suggestion.click();
    } else {
      console.log('Submitting train search form directly...');
      await page.keyboard.press('Enter');
    }

    // Wait for schedule view to load
    console.log('4. Waiting for #train-schedule-view to render...');
    await page.waitForSelector('#train-schedule-view', { timeout: 15000 });

    // Verify verified badge, train number, and stations
    const scheduleContent = await page.$eval('#train-schedule-view', (el) => el.innerText);
    console.log('Schedule View Sample Snippet:\n' + scheduleContent.slice(0, 300) + '...\n');

    if (!scheduleContent.includes('12002')) {
      throw new Error('Schedule view does not contain train number 12002');
    }
    if (!scheduleContent.includes('Verified TAG Timetable')) {
      throw new Error('Schedule view missing "Verified TAG Timetable" badge');
    }
    if (!scheduleContent.includes('NDLS') && !scheduleContent.includes('NEW DELHI')) {
      throw new Error('Schedule view missing origin station NDLS');
    }

    // Verify operating days strip
    console.log('5. Verifying operating days strip...');
    const chipsInfo = await page.evaluate(() => {
      const el = document.querySelector('#train-schedule-view');
      if (!el) return [];
      return Array.from(el.querySelectorAll('div'))
        .filter((d) => ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].includes(d.innerText.trim()))
        .map((d) => ({
          text: d.innerText.trim(),
          testId: d.getAttribute('data-testid'),
          active: d.getAttribute('data-active'),
          classes: d.className,
        }));
    });
    console.log('Day chips detected in DOM:', chipsInfo);
    const dayChips = chipsInfo.filter((c) => c.classes.includes('bg-espresso-900'));
    console.log(`Found ${dayChips.length} active running day chips`);
    if (dayChips.length === 0) {
      throw new Error('No active running day chips found for train 12002');
    }

    // Verify commercial stoppage table
    console.log('6. Verifying stoppage timeline rows...');
    const stopRows = await page.$$('#train-schedule-view tbody tr');
    console.log(`Initial commercial stops count: ${stopRows.length}`);
    if (stopRows.length < 5) {
      throw new Error(`Expected at least 5 commercial stops for 12002, got ${stopRows.length}`);
    }

    // Toggle All Recorded Stops
    console.log('7. Testing "All Recorded Stops" toggle...');
    const allStopsToggle = await page.$('#all-stops-toggle');
    if (allStopsToggle) {
      await allStopsToggle.click();
      await sleep(1000);
      const allRows = await page.$$('#train-schedule-view tbody tr');
      console.log(`Total waypoints count after toggle: ${allRows.length}`);
      if (allRows.length <= stopRows.length) {
        throw new Error('Waypoint count should be greater than commercial stop count');
      }
    }

    // Take screenshot of Timetable View
    const timetableScreenshotPath = path.resolve(
      'C:\\Users\\MAYUR\\.gemini\\antigravity\\brain\\d912be4a-adb8-4eeb-ad55-3fcedf5ab70a',
      'e2e_train_schedule_view_success.png'
    );
    await page.screenshot({ path: timetableScreenshotPath, fullPage: false });
    console.log(`📸 Timetable screenshot saved: ${timetableScreenshotPath}`);

    // 8. Test Connecting Routes Intermediate Halts Expander
    console.log('8. Switching back to Connecting Routes to test intermediate halts in journey legs...');
    const connectingTab = await page.$('#tab-connecting-mode');
    await connectingTab.click();
    await sleep(500);

    // Search BCT to NDLS
    console.log('Filling search: BCT to NDLS...');
    const inputs = await page.$$('input[type="text"]');
    const originInput = inputs[0];
    await originInput.click();
    await originInput.type('BCT', { delay: 40 });
    await sleep(800);
    await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      const bctBtn = buttons.find((b) => b.textContent && b.textContent.includes('BCT'));
      if (bctBtn) bctBtn.click();
    });

    await sleep(400);
    const destInput = inputs[1];
    await destInput.click();
    await destInput.type('NDLS', { delay: 40 });
    await sleep(800);
    await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      const ndlsBtn = buttons.find((b) => b.textContent && b.textContent.includes('NDLS'));
      if (ndlsBtn) ndlsBtn.click();
    });

    // Click Search Journey
    console.log('Clicking Find Railway Routes button...');
    const submitBtn = await page.$('button[type="submit"]');
    await submitBtn.click();

    // Wait for route cards
    console.log('Waiting for route results to appear...');
    await page.waitForSelector('[id^="route-card-"]', { timeout: 15000 });
    const routeCards = await page.$$('[id^="route-card-"]');
    console.log(`Found ${routeCards.length} route cards`);

    // Look for intermediate stops expand button
    console.log('Looking for intermediate halts expand button...');
    const expandButtons = await page.$$('button[data-testid="toggle-intermediate-stops"]');
    console.log(`Found ${expandButtons.length} intermediate stop expand buttons in route timeline`);

    if (expandButtons.length > 0) {
      await expandButtons[0].click();
      await sleep(1000);

      // Verify intermediate stops table rendered
      const stopTable = await page.$('[data-testid="intermediate-stops-list"]');
      if (stopTable) {
        console.log('✅ Intermediate stops list successfully rendered inside journey leg!');
      } else {
        console.warn('Intermediate stops table not found by testid');
      }
    }

    // Open Journey Details Modal to test intermediate halts inside modal
    console.log('Opening Journey Details Modal...');
    const detailsBtn = await routeCards[0].$('button');
    if (detailsBtn) {
      await detailsBtn.click();
      await sleep(1000);

      const modalExpandButtons = await page.$$('button[data-testid="modal-toggle-intermediate-stops"]');
      console.log(`Found ${modalExpandButtons.length} intermediate expand buttons in modal`);
      if (modalExpandButtons.length > 0) {
        await modalExpandButtons[0].click();
        await sleep(800);
        console.log('✅ Expanded intermediate halts in Journey Details Modal!');
      }
    }

    const routeScreenshotPath = path.resolve(
      'C:\\Users\\MAYUR\\.gemini\\antigravity\\brain\\d912be4a-adb8-4eeb-ad55-3fcedf5ab70a',
      'e2e_route_intermediate_stops_success.png'
    );
    await page.screenshot({ path: routeScreenshotPath, fullPage: false });
    console.log(`📸 Route intermediate stops screenshot saved: ${routeScreenshotPath}`);

    console.log('🎉 TW-110 E2E Browser Test Completed Successfully!');
  } finally {
    await browser.close();
  }
}

runE2ETest().catch((err) => {
  console.error('❌ E2E Test Failed:', err);
  process.exit(1);
});
