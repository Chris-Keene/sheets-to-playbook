// Snapshots for tests/golden.py: the text, accessibility tree and a screenshot of each page, slide deck and
// playbook view. Usage: PW=<.../node_modules/playwright> node snap.js <jobs.json> <result.json>
const fs = require("fs");
const path = require("path");
const { chromium } = require(process.env.PW || "playwright");

const [specFile, outFile] = process.argv.slice(2);
const spec = JSON.parse(fs.readFileSync(specFile, "utf8"));
const safe = (k) => k.replace(/[^A-Za-z0-9._-]+/g, "__");

// One line per meaningful node: role, heading level and accessible name. Plain text runs are left to the text
// snapshot, so this shows the structure a screen reader gets: landmarks, headings, links, buttons, lists, images.
const SKIP = new Set(["generic", "none", "StaticText", "InlineTextBox", "LineBreak", "paragraph", "RootWebArea", "presentation"]);
async function axTree(page) {
  const cdp = await page.context().newCDPSession(page);
  const { nodes } = await cdp.send("Accessibility.getFullAXTree");
  const byId = new Map(nodes.map((n) => [n.nodeId, n]));
  const depth = (n) => { let d = 0; while (n.parentId && byId.has(n.parentId)) { n = byId.get(n.parentId); d++; } return d; };
  const lines = [];
  for (const n of nodes) {
    if (n.ignored) continue;
    const role = n.role && n.role.value;
    if (!role || SKIP.has(role)) continue;
    const name = (n.name && n.name.value || "").replace(/\s+/g, " ").trim();
    const level = (n.properties || []).find((p) => p.name === "level");
    lines.push("  ".repeat(Math.min(depth(n), 12)) + role + (level ? `[${level.value.value}]` : "") + (name ? ` "${name}"` : ""));
  }
  await cdp.detach();
  // indentation depth includes wrapper divs, which a refactor may add or remove without changing what's announced
  return lines.map((l) => l.trim()).join("\n") + "\n";
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 }, reducedMotion: "reduce" });
  const result = {};
  for (const job of spec.jobs) {
    const url = "file://" + path.resolve(job.file);
    if (job.kind === "playbook") {
      await page.goto(url);
      for (const r of job.routes) {
        await page.evaluate((h) => { location.hash = h; }, r);
        await page.waitForTimeout(120);
        await page.evaluate(() => document.fonts.ready);
        const key = `${job.key}#${r}`;
        result[key] = { text: await page.evaluate(() => document.body.innerText), ax: await axTree(page) };
        await page.screenshot({ path: path.join(spec.shots, safe(key) + ".png"), fullPage: true });
      }
    } else if (job.kind === "slides") {
      await page.goto(url);
      await page.evaluate(() => document.fonts.ready);
      // only the current slide is visible, so take every slide's text from the markup
      const text = await page.evaluate(() => [...document.querySelectorAll("section")]
        .map((s, i) => `--- slide ${i + 1}\n` + s.textContent.replace(/[ \t]+/g, " ").replace(/\n\s*\n+/g, "\n").trim()).join("\n"));
      result[job.key] = { text, ax: await axTree(page) };
      await page.screenshot({ path: path.join(spec.shots, safe(job.key) + ".png") });
    } else {
      await page.goto(url);
      await page.evaluate(() => document.fonts.ready);
      result[job.key] = { text: await page.evaluate(() => document.body.innerText), ax: await axTree(page) };
      await page.screenshot({ path: path.join(spec.shots, safe(job.key) + ".png"), fullPage: true });
    }
  }
  await browser.close();
  fs.writeFileSync(outFile, JSON.stringify(result));
})().catch((e) => { console.error(e); process.exit(1); });
