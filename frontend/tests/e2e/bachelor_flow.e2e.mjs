/**
 * Browser-based E2E test for Bachelor Special Berth Segment Discovery
 * Tests real end-to-end user interactions on http://localhost:3000
 */

import puppeteer from 'puppeteer-core';
import fs from 'fs';
import { execSync } from 'child_process';

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

async function runBachelorE2ETest() {
  console.log('🚀 Starting Browser-Based E2E Bachelor Special Search Test...');
  const executablePath = findBrowserExecutable();
  console.log(`Using browser executable: ${executablePath}`);

  const browser = await puppeteer.launch({
    executablePath,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  });

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 900 });

    // 1. Navigate to TripWiser Home
    console.log('1. Navigating to http://localhost:3000...');
    const response = await page.goto('http://localhost:3000', {
      waitUntil: 'networkidle2',
      timeout: 30000,
    });
    console.log(`Page HTTP status: ${response.status()}`);
    if (response.status() !== 200) {
      throw new Error(`Expected HTTP 200, got ${response.status()}`);
    }

    // 2. Switch to Bachelor Special tab mode
    console.log('2. Switching to Bachelor Special Mode...');
    await page.waitForSelector('#tab-bachelor-mode', { timeout: 15000 });
    await sleep(1000);
    const bachelorTab = await page.$('#tab-bachelor-mode');
    await bachelorTab.click();
    await page.waitForSelector('#bachelor-search-card', { timeout: 15000 });
    console.log('✓ Successfully activated Bachelor Special search console.');

    // 3. Test Origin Autocomplete: GWL (Gwalior)
    console.log('3. Selecting Origin Station (GWL)...');
    const inputs = await page.$$('#bachelor-search-card input[type="text"]');
    if (inputs.length < 2) {
      throw new Error('Autocomplete inputs not found in Bachelor Search Card');
    }
    const originInput = inputs[0];
    await originInput.click();
    await sleep(200);
    await originInput.type('GWL', { delay: 50 });
    await sleep(800);

    await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      const gwlBtn = buttons.find((b) => b.textContent && b.textContent.includes('GWL'));
      if (gwlBtn) gwlBtn.click();
    });
    await sleep(400);
    console.log('✓ Selected origin station (GWL).');

    // 4. Test Destination Autocomplete: BPL (Bhopal)
    console.log('4. Selecting Destination Station (BPL)...');
    const destInput = inputs[1];
    await destInput.click();
    await sleep(200);
    await destInput.type('BPL', { delay: 50 });
    await sleep(800);

    await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      const bplBtn = buttons.find((b) => b.textContent && b.textContent.includes('BPL'));
      if (bplBtn) bplBtn.click();
    });
    await sleep(400);
    console.log('✓ Selected destination station (BPL).');

    // 5. Test Honest Empty/Uncharted State (Zero-Fabrication)
    console.log('5. Executing search without vacancies to assert zero-fabrication honest response...');
    const searchBtn = await page.$('#bachelor-search-card button[type="submit"]');
    if (!searchBtn) {
      throw new Error('Bachelor submit button not found');
    }
    await searchBtn.click();
    await sleep(1500);

    const emptyNotice = await page.evaluate(() => {
      const text = document.body.innerText;
      return (
        text.includes('No Vacant Berth Segments Observed') ||
        text.includes('Zero-Fabrication Assurance')
      );
    });
    console.log(`✓ Zero-Fabrication disclosure rendered: ${emptyNotice}`);
    if (!emptyNotice) {
      throw new Error('Expected zero-fabrication vacancy disclosure banner');
    }

    // 6. Insert Test Chart Vacancies in Database for train 12002
    console.log('6. Inserting test continuous vacancy records into database for train 12002...');
    const today = new Date();
    today.setDate(today.getDate() + 1);
    const dateStr = today.toISOString().split('T')[0];

    const insertSql = `
      INSERT INTO chart_vacancies (
        id, train_number, chart_date, coach, berth_number, berth_type, travel_class,
        from_station_code, to_station_code, from_sequence, to_sequence, source, chart_phase, status, expires_at
      ) VALUES
      (uuid_generate_v4(), '12002', '${dateStr}', 'B2', 43, 'UB', '3A', 'GWL', 'JHS', 42, 52, 'chart_feed', 'FIRST_CHART', 'VACANT', NOW() + INTERVAL '6 hours'),
      (uuid_generate_v4(), '12002', '${dateStr}', 'B3', 21, 'MB', '3A', 'JHS', 'BPL', 52, 87, 'chart_feed', 'FIRST_CHART', 'VACANT', NOW() + INTERVAL '6 hours');
    `;

    execSync(`docker exec tripwiser-postgres psql -U tripwiser -d tripwiser_db -c "${insertSql.replace(/\n/g, ' ')}"`);
    console.log('✓ Successfully inserted 2 continuous test segments (GWL->JHS and JHS->BPL).');

    // 7. Search again with active vacancies
    console.log('7. Re-running search with active vacancies...');
    await searchBtn.click();
    await sleep(2000);

    await page.waitForSelector('#bachelor-card-0', { timeout: 10000 });
    console.log('✓ Discovered Bachelor Special itinerary card rendered!');

    // 8. Assert Card Contents
    const cardContent = await page.evaluate(() => {
      const card = document.querySelector('#bachelor-card-0');
      if (!card) return null;
      return {
        text: card.innerText,
        hasBerthChange: card.innerText.includes('1 BERTH CHANGE'),
        hasCoachB2: card.innerText.includes('B2') && card.innerText.includes('43'),
        hasCoachB3: card.innerText.includes('B3') && card.innerText.includes('21'),
        hasRelocationNotice: card.innerText.includes('Berth Relocation at JHS'),
        hasPolicyDisclaimer: card.innerText.includes('Bachelor Special Policy'),
      };
    });

    console.log('8. Verifying Card Details:');
    console.log(`   - 1 Berth Change Badge: ${cardContent.hasBerthChange}`);
    console.log(`   - Coach B2 Berth 43: ${cardContent.hasCoachB2}`);
    console.log(`   - Coach B3 Berth 21: ${cardContent.hasCoachB3}`);
    console.log(`   - Berth Relocation at JHS: ${cardContent.hasRelocationNotice}`);
    console.log(`   - Policy Disclaimer: ${cardContent.hasPolicyDisclaimer}`);

    if (
      !cardContent.hasBerthChange ||
      !cardContent.hasCoachB2 ||
      !cardContent.hasCoachB3 ||
      !cardContent.hasRelocationNotice
    ) {
      throw new Error('Card contents did not match expected continuous berth segments');
    }

    // 9. Mobile Viewport Screenshot
    console.log('9. Testing Mobile Viewport (375x812)...');
    await page.setViewport({ width: 375, height: 812, isMobile: true, hasTouch: true });
    await sleep(600);

    const screenshotPath = 'frontend/tests/e2e/e2e_bachelor_special_success.png';
    await page.screenshot({ path: screenshotPath, fullPage: true });
    console.log(`✓ Captured mobile viewport screenshot: ${screenshotPath}`);

    // Clean up test vacancies from database
    console.log('10. Cleaning up test database records...');
    execSync(`docker exec tripwiser-postgres psql -U tripwiser -d tripwiser_db -c "DELETE FROM chart_vacancies WHERE train_number='12002' AND chart_date='${dateStr}';"`);
    console.log('✓ Database cleaned up.');

    console.log('\n🎉 ALL BROWSER-BASED E2E TESTS PASSED FOR BACHELOR SPECIAL! 🎉\n');
  } catch (error) {
    console.error('❌ E2E Test Failed:', error);
    // Cleanup if failure
    try {
      execSync(`docker exec tripwiser-postgres psql -U tripwiser -d tripwiser_db -c "DELETE FROM chart_vacancies WHERE train_number='12002';"`);
    } catch {}
    process.exit(1);
  } finally {
    await browser.close();
  }
}

runBachelorE2ETest();
