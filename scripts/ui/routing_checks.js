/* Execute the shipped console functions against real API fixture responses.
   Node is a test runner only, never a console/runtime dependency. */
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const path = require('path');
const source = fs.readFileSync(path.join(__dirname, 'console.html'), 'utf8');
const fixtures = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1];
new vm.Script(script); // Entire shipped script must parse, not only extracted helpers.
function declaration(name) {
  const start = script.indexOf('function ' + name + '(');
  assert(start >= 0, name);
  const end = script.indexOf('\nfunction ', start + 1);
  return script.slice(start, end < 0 ? script.length : end);
}
const elements = {};
let current = 'a'.repeat(32), human = true;
const context = {
  document: {createElement: () => ({innerHTML: ''}), getElementById: id => elements[id]},
  app: {appendChild: e => { elements[e.id] = e; }},
  currentRoute: () => ({runId: current}), isHumanView: () => human,
  apiJson: async () => ({ok: true, body: fixtures.valid}),
  mutedParen: x => x,
};
vm.createContext(context);
for (const name of ['escapeHtml', 'detailText', 'activationSummaryHtml', 'loadActivation',
                     'mastheadHumanLabel', 'nextActionSentenceHuman', 'renderDetailBody',
                     'citationsHtml', 'wireCitationLinks', 'wireRuleLinks', 'renderSubmit']) {
  vm.runInContext(declaration(name), context);
}
function expectActivity() {
  const html = context.activationSummaryHtml(fixtures.valid, true);
  assert(html.includes('1 dispatch attempts'));
  assert(html.includes('2 explicit non-call decisions'));
  assert(html.includes('1 agents have no reached-phase decision'));
  assert(html.includes('1 recorded execution or preparation failures'));
  assert(html.includes('1 capped replies'));
  assert(html.includes('completed'));
  assert(!html.includes('fixture_call') && !html.includes('<pre>'));
  return html;
}
async function main() {
  const baseline = expectActivity();
  const detailed = context.activationSummaryHtml(fixtures.valid, false);
  for (const value of ['ineligible', 'eligible_inactive', 'phase_not_reached', 'execution_failure', 'fixture_call']) {
    assert(detailed.includes(value));
  }
  for (const name of ['missing', 'invalid', 'mismatch', 'invalid_aggregate']) {
    const html = context.activationSummaryHtml(fixtures[name], true);
    assert(html.includes('unavailable') && !html.includes('0 dispatch attempts'));
  }
  assert(context.activationSummaryHtml(null, true).includes('request_failed'));
  const prepared = context.activationSummaryHtml(fixtures.preparation, true);
  assert(prepared.includes('1 dispatch attempts') && prepared.includes('2 recorded execution or preparation failures'));
  for (const [state, record] of Object.entries(fixtures.completion_states)) {
    assert(context.activationSummaryHtml(record, true).includes('Pipeline completion record: ' + state));
  }
  assert.strictEqual(context.mastheadHumanLabel({state: 'stopped', outcome: 'succeeded'}), 'Process finished');
  assert.strictEqual(context.mastheadHumanLabel({state: 'stopped', outcome: 'governance_stop'}), 'Stopped on purpose');
  assert.strictEqual(context.mastheadHumanLabel({state: 'stopped', outcome: 'crashed'}), 'Stopped by a system fault');
  assert.strictEqual(context.mastheadHumanLabel({state: 'unrecognised'}), 'Unknown');
  assert.strictEqual(context.mastheadHumanLabel(fixtures.statuses.completed), 'Process finished');
  assert.strictEqual(context.mastheadHumanLabel(fixtures.statuses.blocked), 'Stopped on purpose');
  assert.strictEqual(context.mastheadHumanLabel(fixtures.statuses.failed), 'Stopped by a system fault');
  const escaped = JSON.parse(JSON.stringify(fixtures.valid));
  escaped.decisions[0].reason = '<img src=x onerror=alert(1)>';
  assert(!context.activationSummaryHtml(escaped, false).includes('<img'));
  // Neutralise the actual renderer, demand an observed change and failed check.
  const original = context.activationSummaryHtml;
  context.activationSummaryHtml = () => 'No activity';
  assert.notStrictEqual(context.activationSummaryHtml(fixtures.valid, true), baseline);
  assert.throws(expectActivity);
  context.activationSummaryHtml = original;
  assert.strictEqual(expectActivity(), baseline);
  assert.throws(() => { assert.notStrictEqual(expectActivity(), baseline, 'NO_OBSERVED_EFFECT'); });

  let requested;
  context.apiJson = async url => { requested = url; return {ok: true, body: fixtures.valid}; };
  await context.loadActivation(current);
  assert.strictEqual(requested, '/runs/' + current + '/activation');
  assert.strictEqual(elements['activation-summary'].innerHTML, baseline);
  Object.assign(context, {
    stateToken: () => ({tone: 'mint'}), stateDotHtml: () => '',
    runDisplayNameHtml: () => 'Fixture run', loadFindings: () => {}, loadPairs: () => {},
    renderLogPanel: () => {},
  });
  async function renderedActivity() {
    delete elements['activation-summary'];
    context.renderDetailBody({run_id: current, state: 'stopped', outcome: 'succeeded', documents: []}, []);
    await Promise.resolve(); await Promise.resolve();
    return elements['activation-summary'] && elements['activation-summary'].innerHTML;
  }
  assert.strictEqual(await renderedActivity(), baseline);
  assert(!context.app.innerHTML.includes('nothing was checked'));
  const load = context.loadActivation;
  context.loadActivation = () => {};
  const removed = await renderedActivity();
  assert.notStrictEqual(removed, baseline);
  assert.throws(() => assert.strictEqual(removed, baseline));
  context.loadActivation = load;
  assert.strictEqual(await renderedActivity(), baseline);
  // Navigation and replacement guards reject an old asynchronous response.
  let resolve;
  context.apiJson = () => new Promise(r => { resolve = r; });
  const pending = context.loadActivation(current), holder = elements['activation-summary'];
  current = 'b'.repeat(32);
  resolve({ok: true, body: fixtures.valid}); await pending;
  assert(holder.innerHTML.includes('Loading'));
  current = 'a'.repeat(32);
  const replaced = context.loadActivation(current), old = elements['activation-summary'];
  elements['activation-summary'] = {innerHTML: 'new screen'};
  resolve({ok: true, body: fixtures.valid}); await replaced;
  assert(old.innerHTML.includes('Loading'));
  context.apiJson = async () => { throw new Error('offline'); };
  await context.loadActivation(current);
  assert(elements['activation-summary'].innerHTML.includes('request_failed'));

  // Exercise an actual citation click, fed by the authenticated backend fixture.
  const citation = context.citationsHtml(['REF-0001', 'WEB-REF-0001'], current, true);
  assert(citation.includes('data-ref-id="REF-0001"'));
  assert(!citation.includes('data-ref-id="WEB-REF-0001"'));
  let click;
  const anchor = {id: 'fixture-cite', addEventListener: (_, fn) => { click = fn; },
    getAttribute: key => key === 'data-run-id' ? current : 'REF-0001'};
  const panel = {hidden: true}; elements['fixture-cite-panel'] = panel;
  context.apiJson = async url => { requested = url; return {ok: true, body: fixtures.reference}; };
  context.wireCitationLinks({querySelectorAll: () => [anchor]});
  click({preventDefault() {}}); await Promise.resolve(); await Promise.resolve();
  assert.strictEqual(requested, '/runs/' + current + '/references?ref_id=REF-0001');
  assert(panel.innerHTML.includes('Synthetic source passage.'));
  panel.hidden = true; panel._loaded = false;
  context.apiJson = async () => ({ok: false, body: {detail: 'not recorded'}});
  click({preventDefault() {}}); await Promise.resolve(); await Promise.resolve();
  assert(panel.innerHTML.includes('not on record'));
  const ruleAnchor = {id: 'fixture-rule', addEventListener: (_, fn) => { click = fn; },
    getAttribute: () => 'CONV-001'};
  elements['fixture-rule-panel'] = {hidden: true};
  context.apiJson = async url => { requested = url; return {ok: true, body: {id: 'CONV-001', rule: 'Current synthetic rule.'}}; };
  context.wireRuleLinks({querySelectorAll: () => [ruleAnchor]});
  click({preventDefault() {}}); await Promise.resolve(); await Promise.resolve();
  assert.strictEqual(requested, '/rules/CONV-001');
  assert(elements['fixture-rule-panel'].innerHTML.includes('Current synthetic rule.'));
  assert(elements['fixture-rule-panel'].innerHTML.includes('may differ from the rule used by this run'));
  for (const id of ['s-task', 's-files', 's-intake', 'submit-form', 'startup-backend']) {
    elements[id] = {addEventListener() {}, files: []};
  }
  context.apiJson = async () => ({ok: true, body: {backend_profile: 'local'}});
  context.renderSubmit(); await Promise.resolve(); await Promise.resolve();
  assert(context.app.innerHTML.includes('Local Draft is unsupported'));
  assert(elements['startup-backend'].textContent.includes('Local, models on this machine'));
  console.log('PASS: executed console rendering, API binding, unavailable/stale states, view separation, citations, mutation/restoration and no-op refusal');
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
