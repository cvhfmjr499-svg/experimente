// Renders each test frame twice, each time after seeking from a different
// random frame, and checks the screenshots are byte-identical.
const { chromium } = require("playwright");
const path = require("path");
const crypto = require("crypto");
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  await p.goto("file://" + path.resolve(__dirname, "..", "index.html") + "?render=1");
  await p.waitForFunction(() => window.__ready === true);
  const frames = []; for (let f = 0; f < 900; f += 7) frames.push(f);
  let seed = 7; const rand = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  const shot = async (f, from) => { await p.evaluate(x => window.__seek(x), from); await p.evaluate(x => window.__seek(x), f);
    return crypto.createHash("md5").update(await p.screenshot()).digest("hex"); };
  const bad = [];
  for (const f of frames) {
    const a = await shot(f, Math.floor(rand() * 900)), c = await shot(f, Math.floor(rand() * 900));
    if (a !== c) bad.push(f);
  }
  console.log(bad.length ? "NON-DETERMINISTIC frames: " + bad.join(",") : `all ${frames.length} sampled frames deterministic`);
  await b.close();
})();
