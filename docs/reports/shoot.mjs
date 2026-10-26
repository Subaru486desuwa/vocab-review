// 用本机 headless Chromium（DevTools 协议）截取各实验页面；以演示账户 demo 登录，密码取自 .env，不输出。
import { spawn } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";

const [repo, out] = process.argv.slice(2);
const env = Object.fromEntries(readFileSync(`${repo}/.env`, "utf8").split("\n").filter((l) => l.includes("=")).map((l) => [l.slice(0, l.indexOf("=")), l.slice(l.indexOf("=") + 1)]));
const BASE = "http://127.0.0.1:5000";
const chrome = spawn(`${process.env.HOME}/.cache/ms-playwright/chromium_headless_shell-1248/chrome-linux/headless_shell`.replace("chrome-linux/headless_shell", process.argv[4] || "chrome-linux/headless_shell"),
  ["--remote-debugging-port=9333", "--no-sandbox", "--hide-scrollbars", "--lang=zh-CN", `--user-data-dir=${out}/profile`, "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let targets;
for (let i = 0; i < 50; i++) { try { targets = await (await fetch("http://127.0.0.1:9333/json/list")).json(); if (targets.length) break; } catch {} await sleep(200); }
const ws = new WebSocket(targets.find((t) => t.type === "page").webSocketDebuggerUrl);
await new Promise((r) => (ws.onopen = r));
let id = 0; const pending = new Map(); const waiters = [];
ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id); } else if (d.method) { for (const w of waiters.splice(0)) w(d); } };
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const loaded = () => new Promise((r) => { const f = (d) => (d.method === "Page.loadEventFired" ? r() : waiters.push(f)); waiters.push(f); });
const evaluate = async (expr) => (await send("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true })).result?.result?.value;
const go = async (path) => { const l = loaded(); await send("Page.navigate", { url: BASE + path }); await l; await sleep(300); };
const submitAndWait = async (expr) => { const l = loaded(); await evaluate(expr); await l; await sleep(300); };
const until = async (expr) => { for (let i = 0; i < 100; i++) { if (await evaluate(expr)) return; await sleep(100); } throw new Error("等待超时：" + expr); };
// maxHeight 限制截图高度；登录后的概览页只需首屏，下方“近 14 天”另有趋势图。
const shot = async (name, maxHeight = 2400) => {
  const h = await evaluate("Math.ceil(document.documentElement.scrollHeight)");
  await send("Emulation.setDeviceMetricsOverride", { width: 1280, height: Math.min(h, maxHeight), deviceScaleFactor: 1, mobile: false });
  await sleep(200);
  const r = await send("Page.captureScreenshot", { format: "png" });
  writeFileSync(`${out}/${name}.png`, Buffer.from(r.result.data, "base64"));
  await send("Emulation.setDeviceMetricsOverride", { width: 1280, height: 900, deviceScaleFactor: 1, mobile: false });
  console.log("saved", name, h);
};
const fill = (sel, v) => `(() => { const e = document.querySelector(${JSON.stringify(sel)}); e.value = ${JSON.stringify(v)}; e.dispatchEvent(new Event('input', {bubbles: true})); })()`;
// 只截某个元素（例如“近 14 天”表格），不截整页。
const shotElement = async (name, selector) => {
  const box = await evaluate(`(() => { const r = document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect(); return {x: r.x, y: r.y + window.scrollY, width: r.width, height: r.height}; })()`);
  const r = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true, clip: {...box, scale: 1} });
  writeFileSync(`${out}/${name}.png`, Buffer.from(r.result.data, "base64"));
  console.log("saved", name, box.width, box.height);
};

await send("Page.enable"); await send("Runtime.enable");
await send("Emulation.setDeviceMetricsOverride", { width: 1280, height: 900, deviceScaleFactor: 1, mobile: false });
// 实验一
await go("/"); await shot("e1_home");
await go("/lab/hello"); await shot("e1_hello");
// 实验二：登录页、错误密码、正确登录
await go("/login"); await shot("e2_login");
await evaluate(fill("input[name=username]", "demo")); await evaluate(fill("input[name=password]", "wrong-password"));
await submitAndWait("document.querySelector('form.auth-form').submit()"); await shot("e2_login_failed");
await evaluate(fill("input[name=username]", "demo")); await evaluate(fill("input[name=password]", env.DEMO_USER_PASSWORD));
await submitAndWait("document.querySelector('form.auth-form').submit()"); await shot("e2_dashboard", 900);
await go("/dashboard"); await shot("e2_dashboard_stats");
await go("/today"); await shot("e2_today");
await go("/wordbooks"); await until("document.querySelectorAll('#wordbook-list input').length > 0"); await shot("e2_wordbooks");
await go("/practice");
await evaluate("document.querySelector('input[value=recognition]').checked = true"); await evaluate(fill("input[name=count]", "5"));
await evaluate("document.querySelector('#start-form').requestSubmit()"); await until("!document.querySelector('#practice').hidden");
await shot("e2_practice_question");
await evaluate("document.querySelector('#answer-area input').checked = true");
await evaluate("document.querySelector('#answer-form').requestSubmit()"); await until("!document.querySelector('#feedback').hidden");
await shot("e2_practice_feedback");
await go("/review"); await shot("e2_review");
// 实验三
// 报告需要展示离线误差表：截图前展开页面上折叠的“离线评测”。
await go("/lab/ml"); await submitAndWaitResult("#recall-form", "#recall-result");
await evaluate("document.querySelector('details.about').open = true"); await shot("e3_ml");
// 实验四
await go("/examples"); await submitAndWaitResult("#search-form", "#search-result"); await shot("e4_examples");
await evaluate(fill("input[name=text]", "I need to open a savings account at the bank.")); await submitAndWaitResult("#search-form", "#search-result", true); await shot("e4_examples_money");

// 实验二趋势图：改用模拟演示账户 sim_trend（初测时从 daily-dashboard.png 裁图，现已由脚本直接截取）。
await evaluate("document.querySelector('form[action=\"/auth/logout\"]').requestSubmit()");
await sleep(500);
await go("/login");
await evaluate(fill("input[name=username]", process.env.SIM_DEMO_USER || "sim_trend"));
await evaluate(fill("input[name=password]", env.DEMO_USER_PASSWORD));
await submitAndWait("document.querySelector('form.auth-form').submit()");
await go("/dashboard"); await until("document.querySelector('table.trend') !== null");
await shotElement("e2_trend", "table.trend");
await go("/insights"); await until("document.querySelector('.stat-grid') !== null"); await shot("e2_insights", 4200);

async function submitAndWaitResult(form, result, again = false) {
  if (again) await evaluate(`document.querySelector('${result}').hidden = true`);
  await evaluate(`document.querySelector('${form}').requestSubmit()`);
  await until(`!document.querySelector('${result}').hidden`);
  await sleep(200);
}
ws.close(); chrome.kill();
