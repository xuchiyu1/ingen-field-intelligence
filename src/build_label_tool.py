"""Build eval/label_tool.html, an offline page for hand-labelling the gold set.

The page shows one report at a time (text and platform only, no generator
metadata), with keyboard shortcuts and a rule cheat sheet from the Taxonomy
Guide. Labels autosave in the browser; "Export CSV" downloads them, and
src/import_labels.py merges the file into eval/gold_set.csv.

Round 1 labels all 250 reports. Round 2 (a few days later) shows only the 50
double-label reports, without the round-1 answers, for Cohen's kappa.

Usage: python src/build_label_tool.py
"""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CATS = [  # code, shortcut key, one-line rule
    ("H1", "q", "Battery & Power: abnormal drain, BMS warning, power loss, shutdown"),
    ("H2", "w", "Drive & Wheels: wheel, hub motor, suspension hardware fault"),
    ("H3", "e", "Sensors: sensor itself damaged, dirty, miscalibrated, bad data"),
    ("H4", "r", "Charging Dock: can't dock, dock not charging, dock damaged"),
    ("S1", "a", "Navigation: lost, drift, wrong path, low localisation, cautious mode"),
    ("S2", "s", "Obstacle: hit / failed to avoid, or false stop for non-obstacle"),
    ("S3", "d", "Connectivity: WiFi/LTE/link loss, video or calls not getting through"),
    ("S4", "f", "App & Interface: dashboard / app bug, crash, not refreshing"),
    ("S5", "g", "AI Detection Error: sensors fine, AI judgement wrong (false alarm, missed event)"),
    ("E1", "z", "Weather: rain, fog, wind, snow; robot working as designed"),
    ("E2", "x", "Terrain: mud, gravel, sand, flooding; hardware healthy"),
    ("E3", "c", "Access Blocked: gate, construction, parked vehicle, barrier"),
    ("U1", "v", "Interference & Vandalism: stated human action against the robot"),
    ("U2", "b", "User Confusion & Complaints: behaviour, slow replies, voice, confusion"),
    ("NO_INCIDENT", "n", "Designed behaviour / safety rule working / routine note"),
]

PAGE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Gold Set Labelling</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{--bg:#fff;--fg:#1d2433;--muted:#667085;--card:#f4f6f9;--line:#d9dee7;--acc:#2554c7;--on:#e3ebff;--warn:#b45309}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#14171c;--fg:#e6e9ef;--muted:#98a2b3;--card:#1e232b;--line:#333a45;--acc:#7aa2ff;--on:#25304a;--warn:#f59e0b}}
:root[data-theme="dark"]{--bg:#14171c;--fg:#e6e9ef;--muted:#98a2b3;--card:#1e232b;--line:#333a45;--acc:#7aa2ff;--on:#25304a;--warn:#f59e0b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 -apple-system,Segoe UI,Arial,sans-serif}
main{display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:24px;max-width:1200px;margin:0 auto;padding:20px 16px}
@media (max-width:900px){main{grid-template-columns:1fr}}
h1{font-size:20px;margin:0 0 4px}.muted{color:var(--muted)}
.bar{height:6px;background:var(--line);border-radius:3px;overflow:hidden;margin:10px 0 16px}.bar div{height:100%;background:var(--acc)}
.report{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px;font-size:19px;min-height:110px}
.meta{font-size:13px;margin-bottom:8px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px;margin:14px 0}
button{font:inherit;color:var(--fg);background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 10px;cursor:pointer;text-align:left}
button.on{background:var(--on);border-color:var(--acc);font-weight:600}
kbd{font:12px ui-monospace,Menlo,monospace;border:1px solid var(--line);border-radius:4px;padding:0 5px;margin-left:6px;color:var(--muted)}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:10px 0}
textarea{width:100%;font:inherit;color:var(--fg);background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:8px;min-height:54px}
.side{font-size:13px}.side dt{font-weight:600;margin-top:8px}.side dd{margin:0;color:var(--muted)}
.warn{color:var(--warn)}select{font:inherit;color:var(--fg);background:var(--card);border:1px solid var(--line);border-radius:8px;padding:6px}
</style></head><body><main>
<section>
  <h1>Gold set labelling</h1>
  <div class="muted">Label from the Taxonomy Guide only. One primary category: where the robot failed, not the trigger.</div>
  <div class="row"><label>Round <select id="round"><option value="1">1 (all 250)</option><option value="2">2 (50 double-label, days later)</option></select></label>
    <span id="count" class="muted"></span></div>
  <div class="bar"><div id="prog"></div></div>
  <div class="report"><div class="meta muted" id="meta"></div><div id="text"></div></div>
  <div class="grid" id="cats"></div>
  <div class="row"><b>Severity</b><span id="sev"></span></div>
  <div class="row" id="extra"></div>
  <textarea id="notes" placeholder="Notes (why it is borderline, what rule was unclear)"></textarea>
  <div class="row">
    <button id="prev">← Prev</button><button id="next">Next →<kbd>Enter</kbd></button>
    <button id="jump">Next unlabelled</button><button id="export">Export CSV</button>
    <span id="msg" class="muted"></span>
  </div>
</section>
<aside class="side"><h1>Rules</h1><dl id="rules"></dl>
  <p><b>Severity</b> 1 noted, mission continued · 2 interrupted, resumed on its own · 3 human intervention needed · 4 out of service / safety risk. Rate the impact the text reports; if not described, the lowest level it supports.</p>
  <p><b>Root cause stated</b> only if the report itself says why. A guess does not count.</p>
  <p class="muted">Keys: category letters shown on buttons · 1–4 severity · y/u root cause yes/no · k borderline · ← → move.</p>
</aside></main>
<script>
const ROWS = __ROWS__;
const CATS = __CATS__;
const $ = id => document.getElementById(id);
let round = "1", list = [], pos = 0, labels = {};
function key(){ return "goldlabels_r" + round; }
function load(){ try { labels = JSON.parse(localStorage.getItem(key()) || "{}"); } catch(e){ labels = {}; } }
function save(){ try { localStorage.setItem(key(), JSON.stringify(labels)); } catch(e){} }
function cur(){ const id = list[pos].report_id; return labels[id] || (labels[id] = {}); }
function done(l){ return l && l.cat && l.sev && (round === "2" || l.root !== undefined); }
function setRound(r){ round = r; load(); list = ROWS.filter(x => r === "1" || x.double_label === "yes"); pos = 0; jumpUnlabelled(); }
function render(){
  const r = list[pos], l = cur(), n = list.filter(x => done(labels[x.report_id])).length;
  $("meta").textContent = `${pos + 1} / ${list.length} · ${r.report_id} · ${r.platform}`;
  $("text").textContent = r.text;
  $("count").textContent = `${n} of ${list.length} labelled`;
  $("prog").style.width = (100 * n / list.length) + "%";
  $("cats").innerHTML = CATS.map(([c, k, d]) => `<button data-c="${c}" class="${l.cat === c ? "on" : ""}" title="${d}">${c}<kbd>${k}</kbd></button>`).join("");
  $("sev").innerHTML = [1,2,3,4].map(s => `<button data-s="${s}" class="${l.sev == s ? "on" : ""}">${s}</button>`).join(" ");
  $("extra").innerHTML = round === "1"
    ? `<b>Root cause stated</b> <button data-r="yes" class="${l.root === "yes" ? "on" : ""}">yes<kbd>y</kbd></button><button data-r="no" class="${l.root === "no" ? "on" : ""}">no<kbd>u</kbd></button>
       <button data-b="1" class="${l.border ? "on" : ""}">Borderline<kbd>k</kbd></button>`
    : `<span class="muted">Round 2: category and severity only. Don't look at round-1 answers.</span>`;
  $("notes").value = l.notes || "";
}
function set(field, v){ cur()[field] = v; save(); render(); }
function move(d){ cur().notes = $("notes").value; save(); pos = Math.max(0, Math.min(list.length - 1, pos + d)); render(); }
function jumpUnlabelled(){ const i = list.findIndex(x => !done(labels[x.report_id])); pos = i < 0 ? 0 : i; render(); }
document.addEventListener("click", e => {
  const b = e.target.closest("button"); if (!b) return;
  if (b.dataset.c) set("cat", b.dataset.c);
  else if (b.dataset.s) set("sev", b.dataset.s);
  else if (b.dataset.r) set("root", b.dataset.r);
  else if (b.dataset.b) set("border", !cur().border);
});
document.addEventListener("keydown", e => {
  if (e.target === $("notes")) { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); move(1); } return; }
  const c = CATS.find(x => x[1] === e.key);
  if (c) set("cat", c[0]);
  else if ("1234".includes(e.key) && e.key) set("sev", e.key);
  else if (e.key === "y" && round === "1") set("root", "yes");
  else if (e.key === "u" && round === "1") set("root", "no");
  else if (e.key === "k" && round === "1") set("border", !cur().border);
  else if (e.key === "Enter" || e.key === "ArrowRight") move(1);
  else if (e.key === "ArrowLeft") move(-1);
});
$("prev").onclick = () => move(-1); $("next").onclick = () => move(1);
$("jump").onclick = () => { cur().notes = $("notes").value; save(); jumpUnlabelled(); };
$("round").onchange = e => setRound(e.target.value);
$("export").onclick = () => {
  cur().notes = $("notes").value; save();
  const head = round === "1" ? ["report_id","label_category","label_severity","label_root_cause_stated","borderline","notes"]
                             : ["report_id","round2_category","round2_severity"];
  const esc = v => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const lines = [head.join(",")].concat(list.map(r => { const l = labels[r.report_id] || {};
    return (round === "1" ? [r.report_id, l.cat, l.sev, l.root, l.border ? "yes" : "", l.notes] : [r.report_id, l.cat, l.sev]).map(esc).join(","); }));
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([lines.join("\n")], {type: "text/csv"}));
  a.download = `gold_labels_round${round}.csv`; a.click();
  $("msg").textContent = `Exported ${a.download}`;
};
$("rules").innerHTML = CATS.map(([c, k, d]) => `<dt>${c}</dt><dd>${d}</dd>`).join("");
setRound("1");
</script></body></html>
"""


def main():
    rows = list(csv.DictReader(open(ROOT / "eval/gold_set.csv", encoding="utf-8")))
    slim = [{k: r[k] for k in ("report_id", "platform", "text", "double_label")} for r in rows]
    html = (PAGE.replace("__ROWS__", json.dumps(slim, ensure_ascii=False))
                .replace("__CATS__", json.dumps(CATS)))
    out = ROOT / "eval/label_tool.html"
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)} ({len(slim)} reports)")


if __name__ == "__main__":
    main()
