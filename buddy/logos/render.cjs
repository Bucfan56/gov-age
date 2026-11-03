// SVG -> PNG at exact pixel sizes, through Playwright's Chromium (borrowed from daedalus/overseer).
// node render.cjs <svg> <out.png> <size> [<svg> <out.png> <size> ...]
const { chromium } = require("F:/Claude Code/daedalus/overseer/node_modules/playwright");
const fs = require("fs");
(async () => {
  const a = process.argv.slice(2), browser = await chromium.launch();
  for (let i = 0; i < a.length; i += 3) {
    const [src, out, size] = [a[i], a[i + 1], +a[i + 2]];
    const page = await browser.newPage({ viewport: { width: size, height: size } });
    const svg = fs.readFileSync(src, "utf8").replace(/width="512" height="512"/, `width="${size}" height="${size}"`);
    await page.setContent(`<html><body style="margin:0">${svg}</body></html>`);
    await page.screenshot({ path: out, omitBackground: false, clip: { x: 0, y: 0, width: size, height: size } });
    await page.close();
    console.log("wrote", out);
  }
  await browser.close();
})();
