/* Shipped rendering/subscription, authored fixture only, no browser/network. */
"use strict";
const fs = require("fs"), vm = require("vm"), assert = require("assert"), path = require("path");
const source = fs.readFileSync(path.join(__dirname, "../scripts/ui/console.html"), "utf8");
const code = source.slice(source.indexOf("function multiRoundHtml("), source.indexOf("function loadDetail(")) +
  source.slice(source.indexOf("function citationsHtml("), source.indexOf("function wireRuleLinks("));
assert(code.includes("function loadMultiRound("));
const data = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
assert.strictEqual(data.fixture, true);
const nodes = new Map();
let current = "fixture", nextResponse;
const context = {
  escapeHtml: s => String(s).replace(/[&<>"']/g, c => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"}[c])),
  currentRoute: () => ({runId: current}),
  document: {createElement: () => ({querySelectorAll: () => []}), getElementById: id => nodes.get(id)},
  app: {appendChild: el => nodes.set(el.id, el)},
  apiJson: url => { assert(url.endsWith("/multi-round")); return new Promise(resolve => { nextResponse = resolve; }); }
};
vm.createContext(context); vm.runInContext(code, context);
function valid(html) {
  return ["SYNTHETIC FIXTURE", "current positions", "actor history", "issue history", "movements",
    "unresolved", "trajectory", "decision support", "structural comparisons", "evidence", "REF-"].every(s => html.includes(s));
}
(async () => {
  assert(valid(context.multiRoundHtml(data)));
  assert(context.multiRoundHtml(data).includes('data-run-id="' + data.run_id + '"'));
  const original = context.multiRoundHtml;
  context.multiRoundHtml = () => "neutralised";
  let promise = context.loadMultiRound("fixture"); nextResponse({ok:true, body:data}); await promise;
  assert(!valid(nodes.get("multi-round-summary").innerHTML));
  context.multiRoundHtml = original;
  promise = context.loadMultiRound("fixture"); nextResponse({ok:true, body:data}); await promise;
  assert(valid(nodes.get("multi-round-summary").innerHTML));
  const before = original(data); context.multiRoundHtml = original;
  assert.strictEqual(context.multiRoundHtml(data), before); // no-op: NO_OBSERVED_EFFECT
  promise = context.loadMultiRound("fixture"); current = "other";
  nextResponse({ok:true, body:data}); await promise;
  assert.strictEqual(nodes.get("multi-round-summary").innerHTML, undefined);
  current = "fixture"; promise = context.loadMultiRound("fixture");
  nodes.set("multi-round-summary", {}); nextResponse({ok:true, body:data}); await promise;
  assert.strictEqual(nodes.get("multi-round-summary").innerHTML, undefined);
  const attack = JSON.parse(JSON.stringify(data)); attack.view.trajectory[0].text = "<script>fixture</script>";
  assert(!original(attack).includes("<script>"));
  console.log("PASS: fixture projection, real subscription, stale responses, escaping, neutralise/fail/restore/pass; no-op has NO_OBSERVED_EFFECT.");
})().catch(() => { console.error("FAIL: multi-round console fixture"); process.exitCode = 1; });
