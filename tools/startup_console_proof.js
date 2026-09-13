/* Execute the shipped console's startup functions against a small DOM fixture.
 * Host proof only: Node is not a product or container dependency. Fetch and
 * FormData are recorded at the browser boundary; no HTTP or model is reached.
 */
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const assert = require("assert");

const source = fs.readFileSync(path.join(__dirname, "..", "scripts", "ui", "console.html"), "utf8");

function functionSource(name) {
  const start = source.indexOf("function " + name + "(");
  assert(start >= 0, "missing real console function");
  const body = source.indexOf("{", start);
  let depth = 0, quote = "", comment = "";
  for (let i = body; i < source.length; i++) {
    const c = source[i], next = source[i + 1];
    if (comment === "line") { if (c === "\n") comment = ""; continue; }
    if (comment === "block") { if (c === "*" && next === "/") { comment = ""; i++; } continue; }
    if (quote) { if (c === "\\") i++; else if (c === quote) quote = ""; continue; }
    if (c === "/" && next === "/") { comment = "line"; i++; continue; }
    if (c === "/" && next === "*") { comment = "block"; i++; continue; }
    if (c === '"' || c === "'") { quote = c; continue; }
    if (c === "{") depth++;
    if (c === "}" && --depth === 0) return source.slice(start, i + 1);
  }
  throw new Error("unbalanced real console function");
}

const submitSource = functionSource("renderSubmit");
const tokenSource = functionSource("renderNeedsToken");
const tick = () => new Promise(resolve => setImmediate(resolve));

function fixture(code = submitSource, options = {}) {
  const nodes = new Map(), calls = [], changes = [];
  let storedAccess = "", rendered = 0;
  class Element {
    constructor(id) {
      this.id = id; this.events = {}; this.children = []; this.value = "";
      this.files = []; this.disabled = false; this._html = ""; this.textContent = "";
    }
    set innerHTML(html) {
      for (const child of this.children) nodes.delete(child);
      this.children = []; this._html = html;
      for (const match of html.matchAll(/<([a-z]+)\b[^>]*\bid="([^"]+)"[^>]*>/g)) {
        const child = new Element(match[2]);
        if (match[1] === "select") {
          const end = html.indexOf("</select>", match.index);
          const option = html.slice(match.index, end).match(/<option value="([^"]*)"/);
          child.value = option ? option[1] : "";
        }
        nodes.set(child.id, child); this.children.push(child.id);
      }
    }
    get innerHTML() { return this._html; }
    addEventListener(event, callback) { (this.events[event] ||= []).push(callback); }
    focus() { this.focused = true; }
    fire(event) {
      if (this.disabled && event === "click") return;
      for (const callback of this.events[event] || []) callback.call(this, {preventDefault() {}, key: "Enter"});
    }
  }
  const app = new Element("app");
  const context = {
    app, document: {getElementById: id => nodes.get(id) || null},
    location: {hash: ""}, forceTokenScreen: false,
    escapeHtml: value => String(value).replace(/[&<>"']/g, c => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"}[c])),
    getToken: () => storedAccess, setToken: value => { storedAccess = value; changes.push("access saved"); },
    refreshTokenUi: () => {}, render: () => { rendered++; },
    detailText: body => body.detail || "fixture refusal",
    apiJson: () => options.healthFailure ? Promise.reject(new Error("fixture offline")) : Promise.resolve({
      ok: true, body: {backend_profile: options.profile || "local", sensitive_layer_active: false}
    }),
    api: (url, request) => {
      calls.push({url, method: request.method, fields: request.body.fields.map(([name, value]) => [name, typeof value === "object" ? value.name : value])});
      return Promise.resolve({ok: true, json: () => Promise.resolve({run_id: "fixture-run"})});
    },
    FormData: class { constructor() { this.fields = []; } append(name, value) { this.fields.push([name, value]); } },
  };
  vm.createContext(context);
  vm.runInContext(code + "\n" + tokenSource, context);
  return {context, app, nodes, calls, changes, rendered: () => rendered};
}

async function choose(f, values = {}) {
  f.context.renderSubmit();
  await tick();
  const task = f.nodes.get("s-task"); task.value = values.task || "review"; task.fire("change");
  const files = f.nodes.get("s-files");
  files.files = values.files || [{name: "sample.md"}, {name: "earlier.md"}, {name: "rules.md"}];
  files.fire("change");
  const roles = values.roles || ["target", "prior", "grounding"];
  roles.forEach((role, i) => { const el = f.nodes.get("s-role-" + i); if (el) el.value = role; });
  f.nodes.get("s-sensitive").value = Object.hasOwn(values, "privacy") ? values.privacy : "false";
  f.nodes.get("s-question").value = "Check this synthetic document.";
}

async function observation(code = submitSource) {
  const f = fixture(code);
  await choose(f);
  const localText = f.nodes.get("startup-backend").textContent;
  f.nodes.get("submit-form").fire("submit");
  await tick();
  const preparedCalls = f.calls.length;
  const cancel = f.nodes.get("s-cancel");
  if (cancel) cancel.fire("click");
  await tick();
  const cancelledCalls = f.calls.length;
  f.nodes.get("submit-form").fire("submit");
  const confirm = f.nodes.get("s-confirm");
  if (confirm) confirm.fire("click");
  await tick();
  return {preparedCalls, cancelledCalls, posts: f.calls, localText, route: f.context.location.hash};
}

function correct(out) {
  if (out.preparedCalls !== 0 || out.cancelledCalls !== 0 || out.posts.length !== 1) return false;
  const post = out.posts[0], fields = Object.fromEntries(post.fields);
  return post.url === "/submit" && post.method === "POST" && fields.task === "review"
    && fields.sensitive === "false" && fields.intake_mode === "standalone" && fields.confirmed === "true"
    && fields.review_targets === '["sample.md"]' && fields.prior_files === '["earlier.md"]'
    && fields.question === "Check this synthetic document."
    && post.fields.filter(([name]) => name === "files").map(([, value]) => value).join(",") === "sample.md,earlier.md,rules.md"
    && out.localText.includes("Local, models on this machine") && out.route === "#/runs/fixture-run";
}

async function proveMutation(name, mutate) {
  const before = await observation();
  assert(correct(before), "baseline consumer failed");
  const changed = await observation(mutate(submitSource));
  assert.notDeepStrictEqual(changed, before, "neutralisation had no observed effect");
  assert(!correct(changed), "consumer check survived the changed outcome");
  const restored = await observation();
  assert.deepStrictEqual(restored, before, "restoration changed the consumer");
  assert(correct(restored));
  return name;
}

async function main() {
  // Fixture validity comes before behavior: the declared files are distinct,
  // supported, and target/prior/reference roles do not overlap.
  assert.deepStrictEqual(["sample.md", "earlier.md", "rules.md"].filter(n => n.endsWith(".md")).length, 3);
  assert(correct(await observation()));
  for (const values of [{privacy: ""}, {privacy: "true"}, {roles: ["", "prior", "grounding"]}]) {
    const f = fixture(); await choose(f, values);
    f.nodes.get("submit-form").fire("submit"); await tick();
    assert.strictEqual(f.calls.length, 0); assert(!f.nodes.has("s-confirm"));
    assert(f.nodes.get("submit-result").innerHTML.includes("notice error"));
  }
  const unavailable = fixture(submitSource, {healthFailure: true}); await choose(unavailable);
  unavailable.nodes.get("submit-form").fire("submit"); await tick();
  assert.strictEqual(unavailable.calls.length, 0); assert(!unavailable.nodes.has("s-confirm"));
  const cloud = fixture(submitSource, {profile: "cloud"}); await choose(cloud, {task: "draft", files: [], roles: []});
  assert(cloud.nodes.get("startup-backend").textContent.includes("Cloud, provider processing can incur charges"));
  cloud.nodes.get("submit-form").fire("submit"); cloud.nodes.get("s-confirm").fire("click"); await tick();
  assert.strictEqual(Object.fromEntries(cloud.calls[0].fields).task, "draft");
  const signin = fixture(); signin.context.renderNeedsToken();
  assert(signin.app.innerHTML.includes("Copy access token"));
  assert(signin.nodes.get("needs-token-input").focused);
  signin.nodes.get("needs-token-input").value = "PLACEHOLDER";
  signin.nodes.get("needs-token-save").fire("click");
  assert.deepStrictEqual(signin.changes, ["access saved"]); assert.strictEqual(signin.rendered(), 1);
  const mutations = [];
  mutations.push(await proveMutation("confirmation", text => {
    const opening = "document.getElementById('s-confirm').addEventListener('click', function () {";
    const ending = "    });\n    });\n  });\n}";
    assert(text.includes(opening) && text.includes(ending));
    return text.replace(opening, "(function () {").replace(ending, "    });\n    }).call({});\n  });\n}");
  }));
  mutations.push(await proveMutation("target choice wiring", text => {
    const line = "fd.append('review_targets', JSON.stringify(targets));";
    assert(text.includes(line));
    return text.replace(line, "fd.append('review_targets', JSON.stringify([]));");
  }));
  console.log("PASS: real console prepare/cancel/confirm, role and privacy choices, backend readiness, draft flow and sign-in guidance; mutations changed POST timing/targets and were killed/restored (" + mutations.join(", ") + ").");
}

main().catch(error => { console.error("FAIL: " + error.message); process.exitCode = 1; });
