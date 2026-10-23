const out = { steps: [] };
const errs = [];
page.on("pageerror", (e) => errs.push(String(e.message).slice(0, 200)));

const token = process.env.DSH_TEST_TOKEN;
if (!token) { console.error("请先设置环境变量 DSH_TEST_TOKEN（本机 dsh 测试服务的 token），再运行本脚本。"); process.exit(1); }
const base = process.env.DSH_TEST_URL || "http://127.0.0.1:3099/";
await page.goto(base + "?token=" + encodeURIComponent(token), { waitUntil: "domcontentloaded" });
await page.waitForTimeout(6000);

const cont = page.getByRole("button", { name: "继续", exact: true });
if (await cont.count()) { await cont.first().click(); await page.waitForTimeout(1000); out.dismissed = true; }

out.seat = await page.locator(".sk5-root").count();
await page.locator(".sk5-triggerEffort").first().click();
await page.waitForTimeout(700);

const q = async (sel) => (await page.locator(sel).count());
out.struct = {
  head: await q(".ue-head"),
  bolt: await q(".ue-bolt svg"),
  ultra: await page.locator(".ue-ultra").first().innerText().catch(() => null),
  model: await page.locator(".ue-model").first().innerText().catch(() => null),
  reset: await q(".ue-reset"),
  track: await q(".ue-track"),
  particles: await q(".ue-particles i"),
  sliderRole: await page.locator(".ue-track").first().getAttribute("role"),
  ariaNow: await page.locator(".ue-track").first().getAttribute("aria-valuenow"),
};

const box = async (sel) => await page.locator(sel).first().boundingBox();
const bBolt = await box(".ue-bolt");
const bCenter = await box(".ue-center");
const bReset = await box(".ue-reset");
const bPanel = await box(".ue-panel");
out.layout = {
  boltX: Math.round(bBolt.x), centerX: Math.round(bCenter.x), resetX: Math.round(bReset.x),
  panelX: Math.round(bPanel.x), panelW: Math.round(bPanel.width),
  orderOk: bBolt.x < bCenter.x && bCenter.x < bReset.x,
  centerOffset: Math.round((bCenter.x + bCenter.width / 2) - (bPanel.x + bPanel.width / 2)),
};

out.shotPanel = (await page.screenshot({ fullPage: false })).path;
out.errs = errs;
return out;
