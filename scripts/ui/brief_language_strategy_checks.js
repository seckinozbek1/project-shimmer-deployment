/* Execute the shipped case renderer offline with authored API projections. */
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const path = require('path');
const html = fs.readFileSync(path.join(__dirname, 'console.html'), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
new vm.Script(script);
function declaration(name) {
  const start = script.indexOf('function ' + name + '(');
  assert(start >= 0);
  const end = script.indexOf('\nfunction ', start + 1);
  return script.slice(start, end < 0 ? script.length : end);
}
const context = {citationsHtml: () => 'REF-0001'};
vm.createContext(context);
for (const name of ['escapeHtml', 'multiRoundHtml']) vm.runInContext(declaration(name), context);
const fixtures = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
for (const data of fixtures) {
  const rendered = context.multiRoundHtml(data);
  assert(rendered.includes(data.strategic_support.layers[0].display_label));
  assert(rendered.includes(data.strategic_support.state_label));
  assert(!rendered.includes('<script>bad()'));
  assert(rendered.includes('STRATEGIC_OPTION'));
}
assert(html.includes('id="s-language"'));
assert(script.includes("fd.append('output_language', outputLanguage)"));
const escape = context.escapeHtml;
context.escapeHtml = value => String(value);
assert(context.multiRoundHtml(fixtures[0]).includes('<script>bad()'));
context.escapeHtml = escape;
assert(!context.multiRoundHtml(fixtures[0]).includes('<script>bad()'));
process.stdout.write('PASS: actual console renderer, localized labels, escaping and fail/restore proof\n');
