// Headless end-to-end check: full MSME analysis flow in a real browser.
import puppeteer from "puppeteer";

const BASE = "http://localhost:3000";
const consoleErrors = [];
const pageErrors = [];

const browser = await puppeteer.launch({ headless: "new", args: ["--no-sandbox"] });
const page = await browser.newPage();
await page.setViewport({ width: 1440, height: 1000 });
page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text()); });
page.on("pageerror", (e) => pageErrors.push(String(e)));

async function step(name, fn) {
  try { await fn(); console.log(`✓ ${name}`); }
  catch (e) { console.log(`✗ ${name}: ${e.message}`); throw e; }
}

try {
  await step("landing loads", async () => {
    await page.goto(BASE, { waitUntil: "networkidle2", timeout: 60000 });
    await page.waitForSelector("text/IDBI", { timeout: 30000 }).catch(() => {});
  });

  await step("/msmes lists MSMEs", async () => {
    await page.goto(`${BASE}/msmes`, { waitUntil: "networkidle2", timeout: 60000 });
    await page.waitForFunction(() => document.body.innerText.includes("Bharat Textiles"), { timeout: 30000 });
  });

  await step("click Run analysis → navigate to /runs", async () => {
    // click the first Run analysis button (near-miss hero is MSME-001, first card)
    const btn = await page.evaluateHandle(() => {
      const els = [...document.querySelectorAll("button")];
      return els.find((b) => /Run analysis/.test(b.textContent)) || els[0];
    });
    await btn.click();
    await page.waitForFunction(() => location.pathname.startsWith("/runs/"), { timeout: 15000 });
  });

  await step("agent trace appears", async () => {
    await page.waitForFunction(() => document.body.innerText.includes("Agent reasoning trace"), { timeout: 30000 });
  });

  await step("scores + report render", async () => {
    await page.waitForFunction(
      () => document.body.innerText.includes("Health score") &&
             document.body.innerText.includes("PROVENANCE") &&
             document.body.innerText.includes("Credit Intelligence Report"),
      { timeout: 90000 }
    );
  });

  await step("what-if slider works", async () => {
    // click the -20% quick button
    const clicked = await page.evaluate(() => {
      const btn = [...document.querySelectorAll("button")].find((b) => b.textContent.trim() === "−20%");
      if (btn) { btn.click(); return true; } return false;
    });
    if (!clicked) throw new Error("−20% button not found");
    await new Promise((r) => setTimeout(r, 2500));
  });

  await page.screenshot({ path: "e2e-dashboard.png", fullPage: false });
  console.log("📸 screenshot: e2e-dashboard.png");

  // Grab the rendered key numbers for the log
  const summary = await page.evaluate(() => document.body.innerText);
  const grab = (re) => { const m = summary.match(re); return m ? m[0] : null; };
  console.log("Health:", grab(/Health score\s*\n?\s*\d+/));
  console.log("Near-miss visible:", summary.includes("Near-miss inclusion case"));
  console.log("Hindi visible:", /है|सिफारिश/.test(summary));

} catch (e) {
  console.log("E2E FAILED:", e.message);
  await page.screenshot({ path: "e2e-fail.png" }).catch(() => {});
  process.exitCode = 1;
} finally {
  console.log("\nconsole errors:", consoleErrors.length);
  consoleErrors.slice(0, 15).forEach((e) => console.log("  -", e.slice(0, 200)));
  console.log("page errors:", pageErrors.length);
  pageErrors.slice(0, 10).forEach((e) => console.log("  -", e.slice(0, 200)));
  await browser.close();
}