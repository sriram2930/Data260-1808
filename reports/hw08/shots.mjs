// One-off script: screenshots the terminal-look HTML pages (built from
// real captured output by build_terminal_html.py) as PNG images for the
// report. Not part of the graded deliverable.

import { chromium } from "playwright";
import { fileURLToPath } from "url";
import path from "path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const htmlDir = path.join(__dirname, "shots_html");
const outDir = path.join(__dirname, "screenshots");

const PAGES = [
  "p1_docker_ps", "p1_topics_created", "p1_crud_evidence", "p1_worker_log",
  "p1_api_log", "p1_homework_demo", "p1_error_cases",
  "p2_journey",
  "p3_idempotency", "p3_consumer_death", "p3_poison", "p3_ordering",
];

async function main() {
  const browser = await chromium.launch();
  for (const name of PAGES) {
    const page = await browser.newPage({ viewport: { width: 1020, height: 10 } });
    const filePath = "file:///" + path.join(htmlDir, `${name}.html`).replace(/\\/g, "/");
    await page.goto(filePath, { waitUntil: "load" });
    await page.screenshot({ path: path.join(outDir, `${name}.png`), fullPage: true });
    await page.close();
    console.log("shot:", name);
  }
  await browser.close();
  console.log("done");
}

main();
