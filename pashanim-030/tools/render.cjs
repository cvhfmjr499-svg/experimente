// Frame renderer: drives index.html?render=1 with window.__seek(frame) and
// screenshots every frame at 1920x1080 in headless Chromium.
//
//   node tools/render.cjs --out frames            # all frames (timeline.json), 3 workers
//   node tools/render.cjs --out /tmp/x --frames 0,50,100
//   node tools/render.cjs --out /tmp/x --every 20
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const args = process.argv.slice(2);
const opt = (k, d) => { const i = args.indexOf("--" + k); return i >= 0 ? args[i + 1] : d; };
const OUT = path.resolve(opt("out", "frames"));
const WORKERS = +opt("workers", 3);
const FRAMES = JSON.parse(fs.readFileSync(path.resolve(__dirname, "..", "assets/data/timeline.json"))).frames;
let list;
if (opt("frames")) list = opt("frames").split(",").map(Number);
else if (opt("every")) { const e = +opt("every"); list = []; for (let f = 0; f < FRAMES; f += e) list.push(f); }
else list = [...Array(FRAMES).keys()];
const url = "file://" + path.resolve(__dirname, "..", "index.html") + "?render=1";
fs.mkdirSync(OUT, { recursive: true });

(async () => {
  const browser = await chromium.launch({ args: ["--disable-gpu-vsync", "--disable-lcd-text", "--font-render-hinting=none"] });
  const t0 = Date.now();
  let done = 0;
  const chunks = Array.from({ length: WORKERS }, (_, w) => list.filter((_, i) => i % WORKERS === w));
  await Promise.all(chunks.map(async (chunk) => {
    const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
    page.on("pageerror", e => console.error("pageerror:", e.message));
    page.on("console", m => { if (m.type() === "error") console.error("console:", m.text()); });
    await page.goto(url);
    await page.waitForFunction(() => window.__ready === true, null, { timeout: 60000 });
    for (const f of chunk) {
      await page.evaluate(f => window.__seek(f), f);
      await page.screenshot({ path: path.join(OUT, `f${String(f).padStart(4, "0")}.png`), type: "png" });
      done++;
      if (done % 50 === 0) console.log(`${done}/${list.length}  ${((Date.now() - t0) / 1000).toFixed(1)}s`);
    }
    await page.close();
  }));
  await browser.close();
  console.log(`rendered ${list.length} frames in ${((Date.now() - t0) / 1000).toFixed(1)}s -> ${OUT}`);
})();
