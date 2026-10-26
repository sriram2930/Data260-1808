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
  "p1_login", "p1_me", "p1_create_rbac", "p1_delete_rbac", "p1_list",
  "p1_lint_before", "p1_lint_after",
  "p2_tasks", "p2_reliability",
  "p3_reflection",
  "p4_scenario_pay_per_use", "p4_scenario_membership", "p4_snapshot_metadata",
  "p5_attack_results",
  "p6_integration_test", "p6_safety_gate_test",
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
