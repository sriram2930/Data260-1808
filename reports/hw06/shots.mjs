// One-off script: uses Playwright to take real PNG screenshots, both of
// local styled "terminal" pages (built from real captured output by
// build_terminal_html.py) and of the live FastAPI JSON endpoints directly
// in a real browser. Not part of the graded deliverable.

import { chromium } from "playwright";
import { fileURLToPath } from "url";
import path from "path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const htmlDir = path.join(__dirname, "shots_html");
const outDir = path.join(__dirname, "screenshots");

const TERMINAL_PAGES = [
  "p4_consolidation",
  "p4_compliance",
];

const LIVE_URLS = [];

async function main() {
  const browser = await chromium.launch();

  for (const name of TERMINAL_PAGES) {
    const page = await browser.newPage({ viewport: { width: 1020, height: 10 } });
    const filePath = "file:///" + path.join(htmlDir, `${name}.html`).replace(/\\/g, "/");
    await page.goto(filePath, { waitUntil: "load" });
    await page.screenshot({ path: path.join(outDir, `${name}.png`), fullPage: true });
    await page.close();
    console.log("shot:", name);
  }

  for (const { name, url } of LIVE_URLS) {
    const page = await browser.newPage({ viewport: { width: 1100, height: 800 } });
    try {
      await page.goto(url, { waitUntil: "load", timeout: 15000 });
      if (name === "p1_docs_live") {
        await page.waitForTimeout(800);
      }
      await page.screenshot({ path: path.join(outDir, `${name}.png`), fullPage: true });
      console.log("shot:", name);
    } catch (e) {
      console.error("FAILED:", name, e.message);
    }
    await page.close();
  }

  await browser.close();
  console.log("done");
}

main();
