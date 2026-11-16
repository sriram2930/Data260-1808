// Screenshots the REAL running Streamlit dashboard (http://127.0.0.1:8602) for the report.
// Usage: node reports/hw10/dash_shots.mjs [summary|evaluation|trace|all]

import { chromium } from "playwright";
import { fileURLToPath } from "url";
import path from "path";
import fs from "fs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.join(__dirname, "screenshots");
fs.mkdirSync(outDir, { recursive: true });
const URL = "http://127.0.0.1:8602" + (process.argv[3] || "");
const ex = JSON.parse(fs.readFileSync(path.join(__dirname, "raw", "trace_examples.json"), "utf-8"));
const which = process.argv[2] || "all";

async function settle(page) {
  await page.waitForTimeout(2500);
  await page.waitForFunction(() => !document.querySelector('[data-testid="stStatusWidget"]'), null, { timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(1200);
}

async function shot(page, name) {
  await settle(page);
  // grow the viewport to the content height so the whole page is captured (Streamlit scrolls an inner container)
  const h = await page.evaluate(() => {
    const b = document.querySelector('[data-testid="stMainBlockContainer"]');
    return b ? Math.ceil(b.getBoundingClientRect().height) + 160 : 900;
  });
  await page.setViewportSize({ width: 1280, height: Math.min(Math.max(h + 40, 700), 4200) });
  await settle(page);
  await page.screenshot({ path: path.join(outDir, `${name}.png`) });
  console.log("shot:", name);
}

async function nav(page, label) {
  await page.getByText(label, { exact: true }).first().click();
  await settle(page);
}

async function main() {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await page.goto(URL, { waitUntil: "networkidle" });
  await settle(page);
  if (which === "all" || which === "summary") await shot(page, "d1_summary");
  if (which === "all" || which === "evaluation") {
    await nav(page, "Evaluation");
    await shot(page, "d2_evaluation");
    // split into Part 2 / Part 3 images so each stays legible at report width
    const box = await page.getByText("Part 3: is the judge reliable?", { exact: true }).first().boundingBox();
    const full = await page.evaluate(() => document.documentElement.scrollHeight);
    const y = Math.floor(box.y) - 20;
    const vp = page.viewportSize();
    await page.screenshot({ path: path.join(outDir, "d2a_evaluation_part2.png"), clip: { x: 0, y: 0, width: vp.width, height: y } });
    await page.screenshot({ path: path.join(outDir, "d2b_evaluation_part3.png"), clip: { x: 0, y: y, width: vp.width, height: Math.max(vp.height - y, 200) } });
    console.log("shot: d2a/d2b split at", y);
  }
  if (which === "all" || which === "trace") {
    await nav(page, "Trace lookup");
    for (const [key, name] of [["cache_hit", "d3_trace_hit"], ["cache_miss_success", "d3_trace_miss"], ["failed", "d3_trace_failed"]]) {
      const input = page.getByLabel("trace_id");
      await input.fill(ex[key]);
      await input.press("Enter");
      await settle(page);
      await shot(page, name);
    }
  }
  await browser.close();
}

main();
