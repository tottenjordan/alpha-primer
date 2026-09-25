const { chromium } = require('playwright');
const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const TARGET_URL = 'http://127.0.0.1:8080/';
const FRAMES_DIR = '/tmp/dash_frames';
const OUTPUT_GIF = '/usr/local/google/home/jordantotten/alpha/alpha-primer/dashboard/assets/inventory_replenishment_dashboard.gif';

if (!fs.existsSync(FRAMES_DIR)) {
  fs.mkdirSync(FRAMES_DIR, { recursive: true });
}

// Clear any existing frame files
fs.readdirSync(FRAMES_DIR).forEach(f => {
  if (f.endsWith('.png')) fs.unlinkSync(path.join(FRAMES_DIR, f));
});

(async () => {
  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    deviceScaleFactor: 1
  });
  const page = await context.newPage();

  console.log(`Navigating to ${TARGET_URL}...`);
  await page.goto(TARGET_URL, { waitUntil: 'networkidle' });
  await page.waitForTimeout(500);

  async function switchTab(tabId) {
    await page.click(`button[data-tab="${tabId}"]`);
    await page.waitForTimeout(300);
  }

  async function setGen(gen) {
    await page.evaluate((g) => {
      const scrubber = document.getElementById('scrubber');
      if (scrubber) {
        scrubber.value = g;
        scrubber.dispatchEvent(new Event('input', { bubbles: true }));
      }
    }, gen);
    await page.waitForTimeout(300);
  }

  let frameIdx = 0;
  async function capture(caption) {
    const framePath = path.join(FRAMES_DIR, `frame_${String(frameIdx).padStart(2, '0')}.png`);
    await page.screenshot({ path: framePath });
    console.log(`Captured Frame ${frameIdx}: ${caption} -> ${framePath}`);
    frameIdx++;
  }

  // Frame 0: Gen 0 Baseline
  await switchTab('tab-replay');
  await setGen(0);
  await capture('Gen 0 Baseline Static (s, S) Heuristic: $68.4k Cost, 91.2% Fill Rate, 14.6% Spoilage');

  // Frame 1: Gen 8 Breakthrough
  await setGen(8);
  await capture('Gen 8 Censored Demand Imputation Breakthrough: $58.1k Cost (-15.1%)');

  // Frame 2: Gen 17 FIFO Cohort Spoilage Deduction
  await setGen(17);
  await capture('Gen 17 FIFO Spoilage Deduction & Perishability Scaling: $49.2k Cost (-28.1%)');

  // Frame 3: Gen 30 Global Champion
  await setGen(30);
  await capture('Gen 30 Champion Policy: $45.2k Cost (-33.9%), 93.49% Fill Rate, 8.45% Spoilage');

  // Frame 4: What-If Sandbox
  await switchTab('tab-whatif');
  await page.waitForTimeout(300);
  // Trigger a slight slider adjustment to demonstrate responsiveness
  await page.evaluate(() => {
    const slider = document.getElementById('slider-promo');
    if (slider) {
      slider.value = 35;
      slider.dispatchEvent(new Event('input', { bubbles: true }));
    }
  });
  await page.waitForTimeout(300);
  await capture('Interactive What-If Sandbox: Stress-Testing Lead-Time Spikes & Promotional Surges');

  // Frame 5: Benchmark & Math
  await switchTab('tab-benchmark');
  await page.waitForTimeout(300);
  await capture('Benchmark & Verification: Statistical Significance & Closed-Form Perishability Math');

  // Frame 6: Evolved Code Diffs
  await switchTab('tab-diffs');
  await page.waitForTimeout(300);
  await capture('Side-by-Side EVOLVE-BLOCK: Baseline Static (s, S) vs. Gemini 3.5 Flash Champion Code');

  await browser.close();

  console.log(`Stitching ${frameIdx} frames into high-quality animated GIF with ffmpeg...`);
  // Use ffmpeg with high-quality 2-pass palette generation
  const ffmpegCmd = `ffmpeg -y -framerate 0.65 -i ${FRAMES_DIR}/frame_%02d.png ` +
    `-vf "fps=10,scale=1280:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128:stats_mode=diff[p];[s1][p]paletteuse=dither=bayer:bayer_scale=3" ` +
    `${OUTPUT_GIF}`;

  execSync(ffmpegCmd, { stdio: 'inherit' });
  console.log(`Successfully generated GIF at: ${OUTPUT_GIF}`);
})();
