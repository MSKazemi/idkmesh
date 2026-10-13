"""The opt-in reviewer lab stays aligned with the canonical synthetic fixture.

The browser lesson is intentionally NOT a duplicate of the full gate-audit
statistical engine. These checks make its educational outputs reproducible.
"""
from __future__ import annotations

from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "docs" / "labs" / "reviewer-lab.html"
JS = ROOT / "docs" / "labs" / "reviewer-lab.js"
FIXTURE = ROOT / "examples" / "gate-audit" / "panel-votes.example.json"


class _LabParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []
        self.script_data = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.current = dict(attrs)
            self.scripts.append(self.current)

    def handle_data(self, data):
        if self.current and self.current.get("id") == "votes-fixture":
            self.script_data.append(data)

    def handle_endtag(self, tag):
        if tag == "script":
            self.current = None


class ReviewerLabTests(unittest.TestCase):
    def test_synthetic_fixture_is_exactly_embedded(self):
        page = PAGE.read_text(encoding="utf-8")
        parser = _LabParser()
        parser.feed(page)
        actual = json.loads("".join(parser.script_data))
        source = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(source, actual)
        self.assertEqual("synthetic", actual["evidence_class"])
        self.assertEqual(15, len(actual["candidates"]))
        self.assertEqual(5, len(actual["verifiers"]))

    def test_page_has_no_third_party_code_or_tracking(self):
        parser = _LabParser()
        parser.feed(PAGE.read_text(encoding="utf-8"))
        self.assertEqual(
            ["reviewer-lab.js"],
            [script["src"] for script in parser.scripts if "src" in script],
        )
        js = JS.read_text(encoding="utf-8")
        self.assertNotIn("fetch(", js)
        self.assertNotIn("XMLHttpRequest", js)
        self.assertNotIn("localStorage", js)
        self.assertNotIn("innerHTML", js)
        self.assertIn("accept_votes > quorum * total", js)

    def test_learning_page_accessibility_and_link(self):
        page = PAGE.read_text(encoding="utf-8")
        for marker in (
            'lang="en"', '<main id="main"', 'aria-live="polite"',
            'name="lab-reviewer"', 'id="lab-candidate"',
            'id="lab-reset"', '<noscript>',
            "known-bad", "synthetic", "not the same thing as independent verification",
        ):
            self.assertIn(marker, page)
        for path in ("README.md", "docs/start.html", "docs/BEGINNER_GUIDE.md"):
            self.assertIn("reviewer-lab.html", (ROOT / path).read_text(encoding="utf-8"))
        sitemap = (ROOT / "docs/sitemap.xml").read_text(encoding="utf-8")
        self.assertEqual(1, sitemap.count("<loc>https://mskazemi.com/idkmesh/labs/reviewer-lab.html</loc>"))

    def test_js_calculator_parity_on_default_and_subsets(self):
        # Node is optional for Python-only contributor setups; browser code is
        # tested without a DOM using the exported pure function when available.
        import shutil
        if not shutil.which("node"):
            self.skipTest("node is not installed")
        fixture_path = str(FIXTURE)
        js_path = str(JS)
        code = """
const assert = require("node:assert/strict");
const fixture = require(process.argv[1]);
const {analyze} = require(process.argv[2]);
const all = fixture.verifiers.map(x => x.id);
function expected(ids, q) {
  let normalFA = 0, normalFR = 0, probeBreaches = 0;
  for (const c of fixture.candidates) {
    const approvals = fixture.verifiers.filter(v =>
      ids.includes(v.id) && v.verdicts[c.id] === "accept").length;
    const accepted = approvals > q * ids.length;
    if(c.probe && accepted) probeBreaches++;
    if(!c.probe && accepted && c.ground_truth === "reject") normalFA++;
    if(!c.probe && !accepted && c.ground_truth === "accept") normalFR++;
  }
  return [normalFA, normalFR, probeBreaches];
}
const baseline = analyze(fixture, all, 0.5);
assert.deepEqual(
  [baseline.falseAccepts, baseline.falseRejects, baseline.probeBreaches],
  [1, 1, 2]
);
assert.deepEqual(baseline.pairs[0].sharedIds, ["c03", "c07", "c10"]);
for(let mask=1; mask<32; mask++) {
 const ids = all.filter((_, i) => mask & (1 << i));
 for(const quorum of [0.5, 0.67, 0.8]) {
  const r = analyze(fixture, ids, quorum);
  assert.deepEqual([r.falseAccepts, r.falseRejects, r.probeBreaches],
    expected(ids, quorum));
  assert.equal(r.requiredApprovals, Math.floor(quorum * ids.length) + 1);
 }
}
console.log("93 deterministic lab combinations verified");
"""
        result = subprocess.run(
            ["node", "-e", code, fixture_path, js_path],
            cwd=ROOT, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("93 deterministic", result.stdout)


    def test_dom_controls_have_reproducible_effects(self):
        """Exercise the actual browser script using minimal deterministic DOM nodes."""
        import shutil
        if not shutil.which("node"):
            self.skipTest("node is not installed")
        code = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const page = fs.readFileSync(process.argv[1], 'utf8');
const script = fs.readFileSync(process.argv[2], 'utf8');
const json = page.match(/<script id="votes-fixture" type="application\/json">([\s\S]*?)<\/script>/);
assert.ok(json, 'missing fixture');
const fixture = JSON.parse(json[1]);
class Element {
  constructor(tag, id) {
    this.tag = tag; this.id = id; this.children = [];
    this.textContent = ''; this.value = ''; this.checked = false;
    this.hidden = false; this.listeners = {}; this.attrs = {}; this.className = '';
  }
  appendChild(child) { this.children.push(child); return child; }
  replaceChildren(...children) { this.children = children; }
  addEventListener(type, fn) { this.listeners[type] = fn; }
  setAttribute(key, value) { this.attrs[key] = value; }
  focus() { this.focused = true; }
  fire(type) {
    assert.ok(this.listeners[type], 'missing '+type+' handler on '+this.id);
    this.listeners[type]();
  }
}
const ids = [
  'votes-fixture', 'lab-error', 'lab-quorum', 'lab-candidate', 'lab-live',
  'lab-votes', 'lab-rows', 'lab-required', 'lab-false-accepts',
  'lab-false-rejects', 'lab-breaches', 'lab-truth', 'lab-panel',
  'lab-status', 'lab-vote-count', 'lab-candidate-context',
  'lab-pair-summary', 'lab-reset', 'lab-example-probe', 'lab-example-shared'
];
const nodes = Object.fromEntries(ids.map(id => [id, new Element('div', id)]));
nodes['votes-fixture'].textContent = json[1];
nodes['lab-quorum'].value = '0.5';
const checkboxes = fixture.verifiers.map(v => {
  const box = new Element('input', v.id);
  box.value = v.id; box.checked = true; return box;
});
const doc = {
  readyState: 'complete',
  getElementById: id => nodes[id],
  createElement: tag => new Element(tag),
  querySelectorAll: selector => {
    assert.equal(selector, 'input[name="lab-reviewer"]');
    return checkboxes;
  }
};
new Function('document', 'module', script)(doc, undefined);
function outcomes() {
  return [nodes['lab-false-accepts'].textContent,
          nodes['lab-false-rejects'].textContent,
          nodes['lab-breaches'].textContent];
}
assert.deepEqual(outcomes(), ['1 / 12', '1 / 12', '2 / 3']);
assert.equal(nodes['lab-candidate'].children.length, 15);
assert.equal(nodes['lab-rows'].children.length, 15);
assert.equal(nodes['lab-votes'].children.length, 5);
assert.match(nodes['lab-status'].textContent, /Mistake/);

nodes['lab-quorum'].value = '0.67';
nodes['lab-quorum'].fire('change');
assert.deepEqual(outcomes(), ['0 / 12', '2 / 12', '0 / 3']);
nodes['lab-example-shared'].fire('click');
assert.equal(nodes['lab-candidate'].value, 'c10');
assert.match(nodes['lab-status'].textContent, /Matches/);
nodes['lab-reset'].fire('click');
assert.equal(nodes['lab-candidate'].value, 'p01');
assert.equal(nodes['lab-quorum'].value, '0.5');
assert.deepEqual(outcomes(), ['1 / 12', '1 / 12', '2 / 3']);
for(let i=0; i<4; i++) {
  checkboxes[i].checked = false;
  checkboxes[i].fire('change');
}
checkboxes[4].checked = false;
checkboxes[4].fire('change');
assert.equal(checkboxes[4].checked, true);
assert.equal(nodes['lab-error'].hidden, false);
console.log('reviewer lab DOM controls pass');
"""
        result = subprocess.run(
            ["node", "-e", code, str(PAGE), str(JS)],
            cwd=ROOT, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("reviewer lab DOM controls pass", result.stdout)


if __name__ == "__main__":
    unittest.main()
