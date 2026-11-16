// One-off script: screenshots the terminal-look HTML pages (built from real captured output by
// build_terminal_html.py) as PNG images for the report.

import { chromium } from "playwright";
import { fileURLToPath } from "url";
import path from "path";
import fs from "fs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const htmlDir = path.join(__dirname, "shots_html");
const outDir = path.join(__dirname, "screenshots");
fs.mkdirSync(outDir, { recursive: true });

const PAGES = fs.readdirSync(htmlDir).filter((f) => f.endsWith(".html") && !f.startsWith("_")).map((f) => f.replace(".html", ""));

async function main() {
  const browser = await chromium.launch();
  for (const name of PAGES) {
    const page = await browser.newPage({ viewport: { width: 1020, height: 10 } });
    await page.goto("file:///" + path.join(htmlDir, `${name}.html`).replace(/\\/g, "/"), { waitUntil: "load" });
    await page.screenshot({ path: path.join(outDir, `${name}.png`), fullPage: true });
    await page.close();
    console.log("shot:", name);
  }
  await browser.close();
}

main();
