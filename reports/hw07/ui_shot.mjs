// One-off script: drives the real bike-share UI (Part-8/ui_server.py) with
// Playwright -- uploads the real scenario CSV, submits the real question,
// waits for the real agent run to finish, and screenshots the resulting
// timeline + results panels. Not part of the graded deliverable.

import { chromium } from "playwright";
import path from "path";

const CSV_PATH = path.resolve("Part-8/data/scenario_pay_per_use.csv");
const OUT_PATH = path.resolve("reports/hw07/screenshots/p4_ui_run.png");

async function main() {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1000, height: 1400 } });
  await page.goto("http://127.0.0.1:8009/", { waitUntil: "load" });

  await page.setInputFiles("#csv_file", CSV_PATH);
  console.log("submitting, waiting for agent run (can take 1-2 minutes)...");
  await page.click("#runBtn");

  await page.waitForSelector("#resultsPanel", { state: "visible", timeout: 180000 });
  await page.waitForTimeout(500);

  await page.screenshot({ path: OUT_PATH, fullPage: true });
  console.log("shot:", OUT_PATH);

  await browser.close();
}

main();
