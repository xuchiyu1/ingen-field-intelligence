// Build W04_Findings_Deck.pptx: 8 slides, every title a finding.
// Numbers come from results/w03/*.json and the Week 2 run logs, so the deck
// rebuilds with the analysis. Export to PDF from PowerPoint or Keynote.
//
// Usage: npm install pptxgenjs@3.12.0 && node src/make_deck.js
//        (applyTheme path: set PPTX_SKILL to the pptx skill directory, optional)

const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const ROOT = path.resolve(__dirname, "..");
const read = (p) => JSON.parse(fs.readFileSync(path.join(ROOT, p), "utf8"));
const tr = read("results/w03/trends_summary.json");
const te = read("results/w03/telemetry_summary.json");
const ak = read("results/w03/answer_key_check.json");
const auc = Object.fromEntries(te.cv_auc.map((r) => [r.target, r.auc_mean]));
const p1 = ak.P1_navigation_hotspot.found_with_predicted_labels;

const THEME = {
  name: "Field Intelligence", headFontFace: "Cambria", bodyFontFace: "Calibri",
  colors: { dk1: "14213D", lt1: "FFFFFF", dk2: "3D4A63", lt2: "EEF1F6",
            accent1: "F2A007", accent2: "2A78D6", accent3: "667085", accent4: "1BAF7A",
            accent5: "EB6834", accent6: "9AA4B5", hlink: "2A78D6", folHlink: "667085" },
};
const C_HEX = THEME.colors;

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";               // 10 x 5.625 in
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.author = "Chiyu Xu";
pres.title = "inGen Field Intelligence: Findings";
const C = pres.SchemeColor;

const titleOpts = (color) => ({ x: 0.5, y: 0.35, w: 9.0, h: 0.95, fontSize: 26, bold: true,
                                color, valign: "top", fontFace: THEME.headFontFace });
pres.defineSlideMaster({
  title: "DARK", background: { color: C_HEX.dk1 },
  objects: [{ placeholder: { options: { name: "title", type: "title", ...titleOpts(C.background1) },
                             text: "" } }],
  slideNumber: { x: 9.2, y: 5.2, w: 0.5, h: 0.3, fontSize: 10, color: C_HEX.accent6 },
});
pres.defineSlideMaster({
  title: "LIGHT", background: { color: C_HEX.lt1 },
  objects: [{ placeholder: { options: { name: "title", type: "title", ...titleOpts(C.text1) },
                             text: "" } }],
  slideNumber: { x: 9.2, y: 5.2, w: 0.5, h: 0.3, fontSize: 10, color: C_HEX.accent3 },
});

function badge(slide, n, x, y, name) {   // motif: amber numbered circle
  slide.addShape(pres.shapes.OVAL, { x, y, w: 0.42, h: 0.42, fill: { color: C.accent1 },
                                     line: { color: C.accent1 }, objectName: `${name}-badge` });
  slide.addText(String(n), { x, y, w: 0.42, h: 0.42, fontSize: 14, bold: true, align: "center",
                             valign: "middle", color: C.text1, margin: 0, isTextBox: true,
                             objectName: `${name}-badge-n` });
}

function stat(slide, x, y, w, big, label, dark, name) {
  slide.addText(big, { x, y, w, h: 0.8, fontSize: 40, bold: true, margin: 0, isTextBox: true,
                       color: dark ? C.accent1 : C.text1, fontFace: THEME.headFontFace, objectName: name });
  slide.addText(label, { x, y: y + 0.8, w, h: 0.75, fontSize: 12, margin: 0, isTextBox: true,
                         valign: "top", color: dark ? C.background2 : C.text2, objectName: `${name}-label` });
}

function caption(slide, text, y = 5.05) {
  slide.addText(text, { x: 0.5, y, w: 8.5, h: 0.35, fontSize: 10, italic: true, margin: 0,
                        isTextBox: true, color: C.accent3, objectName: "caption" });
}

// 1. Problem ---------------------------------------------------------------
let s = pres.addSlide({ masterName: "DARK" });
s.addText("Robot field reports hold early warnings that nobody has time to read", { placeholder: "title" });
s.addText("inGen Field Intelligence · Chiyu Xu · Applied AI Analyst Intern", {
  x: 0.5, y: 1.35, w: 9, h: 0.35, fontSize: 13, color: C.background2, margin: 0, isTextBox: true });
stat(s, 0.5, 2.3, 2.7, "2,000", "free-text reports from Aido Rover and Fari (synthetic, Jan–Jun 2026)", true, "s1-a");
stat(s, 3.6, 2.3, 2.7, "14", "incident categories plus No Incident, with severity 1–4", true, "s1-b");
stat(s, 6.7, 2.3, 2.7, "4", "hidden patterns planted and sealed, to test whether the analysis finds them", true, "s1-c");
s.addNotes("Operators, technicians and care staff write short, messy notes. Nobody reads 2,000 of them, so " +
  "recurring problems stay invisible. This project turns them into a measured classification and tested findings. " +
  "All data is synthetic, with four patterns planted and sealed so we can check what the method finds and misses.");

// 2. Approach --------------------------------------------------------------
s = pres.addSlide({ masterName: "LIGHT" });
s.addText("Four steps turn messy notes into tested, rate-based findings", { placeholder: "title" });
const steps = [
  ["Taxonomy", "14 categories by where the robot failed, not the trigger; severity 1–4"],
  ["Gold set", "250 reports labelled by hand; 150 to tune, 100 held out and scored once"],
  ["LLM classifier", "Versioned prompt, JSON schema, retry then flag; cost logged per run"],
  ["Analysis", "Rates per operating hour, confidence intervals, multiple-testing correction"],
];
steps.forEach(([h, d], i) => {
  const x = 0.5 + i * 2.3;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.75, w: 2.05, h: 2.6, rectRadius: 0.12,
    fill: { color: C.background2 }, line: { color: C.background2 }, objectName: `step${i}-card` });
  badge(s, i + 1, x + 0.2, 1.95, `step${i}`);
  s.addText(h, { x: x + 0.2, y: 2.5, w: 1.7, h: 0.4, fontSize: 16, bold: true, color: C.text1,
                 margin: 0, isTextBox: true, objectName: `step${i}-h` });
  s.addText(d, { x: x + 0.2, y: 2.95, w: 1.7, h: 1.3, fontSize: 12, color: C.text2, margin: 0,
                 valign: "top", isTextBox: true, objectName: `step${i}-d` });
});
caption(s, "One command (python run_all.py) rebuilds every number and figure in this deck.", 4.7);
s.addNotes("The key discipline: the held-out set was used once, for the final number, so the accuracy is not " +
  "tuned to the test. Every comparison uses incidents per operating hour, because busier sites naturally report more.");

// 3. Accuracy --------------------------------------------------------------
s = pres.addSlide({ masterName: "LIGHT" });
s.addText("The LLM classifier is 96% accurate on unseen reports, ahead of both baselines", { placeholder: "title" });
s.addChart(pres.charts.BAR, [{ name: "Accuracy", labels: ["LLM classifier", "Keyword rules", "TF-IDF + logistic"],
                               values: [96.0, 94.0, 78.0] }], {
  x: 0.5, y: 1.45, w: 5.2, h: 3.4, barDir: "bar", chartColors: [C_HEX.accent2],
  showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: '0.0"%"', dataLabelFontSize: 12,
  dataLabelColor: C_HEX.dk1, dataLabelFontFace: "+mn-lt",
  catAxisLabelColor: C_HEX.dk2, catAxisLabelFontSize: 12, catAxisLabelFontFace: "+mn-lt",
  catAxisOrientation: "maxMin", valAxisHidden: true, valAxisMinVal: 0, valAxisMaxVal: 100,
  valGridLine: { style: "none" }, catGridLine: { style: "none" }, showLegend: false,
  showTitle: true, title: "Category accuracy, 100 held-out reports", titleFontSize: 12,
  titleColor: C_HEX.dk2, titleFontFace: "+mn-lt", objectName: "accuracy-chart" });
s.addText([
  { text: "Human review: ", options: { bold: true } },
  { text: "every confidence band met the 80% floor; only 1.6% of outputs are low-confidence.",
    options: { breakLine: true } },
  { text: " ", options: { breakLine: true, fontSize: 6 } },
  { text: "Main error: ", options: { bold: true } },
  { text: "a patrol paused by the weather rule is read as either Weather or No Incident (27 of 2,000). " +
          "The fix is one sentence in the taxonomy, not a new model." },
], { x: 6.0, y: 1.6, w: 3.5, h: 3.2, fontSize: 14, color: C.text1, valign: "top", margin: 0,
     isTextBox: true, objectName: "accuracy-notes" });
caption(s, `Against the generator's own labels: ${(ak.classifier_vs_generator.category_accuracy * 100).toFixed(1)}% on all 2,000 reports.`);
s.addNotes("Keyword rules are close because the synthetic text is template-based; on real notes the gap should " +
  "be larger. The value of the LLM is that it also returns a reason and a confidence, which lets us route doubtful " +
  "cases to a person.");

// 4. What goes wrong most -------------------------------------------------
s = pres.addSlide({ masterName: "LIGHT" });
s.addText("Cold nights and the April Fari update drive the biggest rises in incidents", { placeholder: "title" });
stat(s, 0.5, 1.4, 4.2, `${tr.cold_battery.h1_rate_ratio_cold_vs_warm}×`,
     `battery incident rate below 0 °C (95% CI ${tr.cold_battery.ci[0]}–${tr.cold_battery.ci[1]})`, false, "s4-a");
stat(s, 5.2, 1.4, 4.3, `${tr.fari.delay_rate_ratio_after_vs_before.toFixed(1)}×`,
     `Fari response-delay complaints after 1 April (95% CI ${tr.fari.ci[0]}–${tr.fari.ci[1]}); ` +
     `latency ${tr.fari.mean_latency_s_before} s → ${tr.fari.mean_latency_s_after} s`, false, "s4-b");
s.addImage({ path: path.join(ROOT, "figures/w03_weekly_rates.png"), x: 0.5, y: 2.95, w: 6.4, h: 2.09,
             altText: "Weekly incident rates: Rover battery vs navigation, and Fari delay complaints with the April 1 update marked" });
s.addText("Severity cannot be ranked yet: predicted severity matched hand labels only 47% of the time.", {
  x: 7.15, y: 3.1, w: 2.35, h: 1.8, fontSize: 12, color: C.text2, valign: "top", margin: 0,
  isTextBox: true, objectName: "severity-note" });
s.addNotes("Both are rate ratios per operating hour with confidence intervals, not raw counts. The Fari rise starts " +
  "the week of the update, but a before-after comparison alone cannot prove the update caused it. Severity is " +
  "weak because the reports rarely say how bad the impact was.");

// 5. Hotspot ----------------------------------------------------------------
s = pres.addSlide({ masterName: "LIGHT" });
s.addText("Site_C North has the most navigation incidents, but the data cannot yet confirm a hotspot", { placeholder: "title" });
s.addImage({ path: path.join(ROOT, "maps/w03_s1_hotspot.png"), x: 0.5, y: 1.45, w: 9.0, h: 2.25,
             altText: "Navigation incidents per 100 operating hours for the 25 patrol zones; Site_C North is highest" });
stat(s, 0.5, 3.8, 2.6, `${p1.rr}×`, "the fleet's navigation rate, highest of 25 zones", false, "s5-a");
stat(s, 3.4, 3.8, 2.6, `q = ${p1.q_bh_25_zones.toFixed(2)}`, "after correcting for 25 zones: not significant", false, "s5-b");
s.addText("15 zone–category cells pass p < 0.05, about what 350 tests give by chance. Treat Site_C North as a lead to check, not a finding.", {
  x: 6.4, y: 3.8, w: 3.1, h: 1.3, fontSize: 12, color: C.text2, valign: "top", margin: 0,
  isTextBox: true, objectName: "hotspot-note" });
s.addNotes("I tested each zone's rate against the rest of the fleet and corrected for multiple testing. Getis-Ord " +
  "Gi* was also run, but with 25 zones and one to four neighbours each its p-values are unstable, so it is context " +
  "only. Live demo: open maps/w03_s1_hotspot.png after python run_all.py.");

// 6. Telemetry -------------------------------------------------------------
s = pres.addSlide({ masterName: "LIGHT" });
s.addText("Rising motor current warns of sensor faults; most other incidents leave no trace", { placeholder: "title" });
s.addImage({ path: path.join(ROOT, "figures/w03_motor_current.png"), x: 0.5, y: 1.45, w: 5.6, h: 1.79,
             altText: "Motor current and its trend are higher in the hour before a sensor fault than in normal hours" });
stat(s, 6.5, 1.4, 3.0, auc.H3.toFixed(3), "cross-validated AUC: sensor-fault hours vs normal hours", false, "s6-a");
const rows = [["Signal in the hour before", "AUC"],
  ["Sensor fault: motor current trend", auc.H3.toFixed(3)], ["Battery: charge and drain", auc.H1.toFixed(3)],
  ["Navigation: localisation confidence", auc.S1.toFixed(3)],
  ["Obstacle, connectivity, app, access", "≈ 0.5"]];
s.addTable(rows.map((r, i) => r.map((t) => ({ text: t, options: { bold: i === 0, color: C_HEX.dk1,
    fill: { color: i === 0 ? C_HEX.lt2 : C_HEX.lt1 } } }))), {
  x: 0.5, y: 3.45, w: 5.6, colW: [4.4, 1.2], fontSize: 12, fontFace: THEME.bodyFontFace,
  border: { type: "solid", pt: 0.5, color: C_HEX.lt2 }, rowH: 0.3, objectName: "auc-table" });
s.addText("Battery and navigation AUCs partly restate the label. The useful signal is the non-obvious one: the drive motor warns of a sensor fault.", {
  x: 6.5, y: 3.45, w: 3.0, h: 1.5, fontSize: 12, color: C.text2, valign: "top", margin: 0,
  isTextBox: true, objectName: "telemetry-note" });
s.addNotes("Compared with 2,353 normal-operation windows, using 5-fold cross-validation. The telemetry is synthetic, " +
  "so these AUCs are an upper bound; the next step is to check this on real telemetry.");

// 7. Limitations -------------------------------------------------------------
s = pres.addSlide({ masterName: "LIGHT" });
s.addText("These findings come from synthetic data, and one planted pattern was only partly found", { placeholder: "title" });
const key = [["Planted pattern", "Result"],
  ["Cold-weather battery incidents", "Found"], ["Fari delay complaints after update", "Found"],
  ["Motor current before sensor faults", "Found"], ["Site_C North navigation hotspot", "Partial: sample too small"]];
s.addTable(key.map((r, i) => r.map((t) => ({ text: t, options: { bold: i === 0, color: C_HEX.dk1,
    fill: { color: i === 0 ? C_HEX.lt2 : C_HEX.lt1 } } }))), {
  x: 0.5, y: 1.5, w: 5.0, colW: [3.0, 2.0], fontSize: 13, fontFace: THEME.bodyFontFace,
  border: { type: "solid", pt: 0.5, color: C_HEX.lt2 }, rowH: 0.42, objectName: "answer-key-table" });
s.addText([
  { text: "All data is synthetic", options: { bold: true, bullet: true, breakLine: true } },
  { text: "Reports, operating hours and telemetry were generated, so results show what the method can detect.",
    options: { breakLine: true } },
  { text: "One labeller", options: { bold: true, bullet: true, breakLine: true } },
  { text: "Kappa 1.0 was a same-day re-label and overstates reliability.", options: { breakLine: true } },
  { text: "The miss is sample size", options: { bold: true, bullet: true, breakLine: true } },
  { text: "With the true labels the hotspot is still not significant." },
], { x: 5.9, y: 1.5, w: 3.6, h: 3.4, fontSize: 13, color: C.text1, valign: "top", margin: 0,
     paraSpaceAfter: 4, isTextBox: true, objectName: "limits" });
s.addNotes("The answer key was sealed with a published hash and opened only after the analysis was final. " +
  "Re-running the hotspot test with the generator's true labels shows the miss is not the classifier: about 63 " +
  "reports per zone is too few.");

// 8. Next steps --------------------------------------------------------------
s = pres.addSlide({ masterName: "DARK" });
s.addText("Next: run the pipeline on real InGen reports and turn the sensor signal into an alert", { placeholder: "title" });
const next = [
  ["Real reports", "Run on a month of real field notes with names removed; label 50 per month to watch accuracy."],
  ["Sentinel Prime logs", "Add alert logs as a second text source and link alerts to incidents."],
  ["Maintenance alert", "Validate the motor-current signal on real telemetry, then alert on a rising trend."],
];
next.forEach(([h, d], i) => {
  const x = 0.5 + i * 3.07;
  badge(s, i + 1, x, 1.8, `next${i}`);
  s.addText(h, { x, y: 2.4, w: 2.8, h: 0.4, fontSize: 16, bold: true, color: C.background1,
                 margin: 0, isTextBox: true, objectName: `next${i}-h` });
  s.addText(d, { x, y: 2.85, w: 2.8, h: 1.4, fontSize: 13, color: C.background2, valign: "top",
                 margin: 0, isTextBox: true, objectName: `next${i}-d` });
});
s.addText("Quick wins: fix the weather-pause rule; check the April Fari release for latency.", {
  x: 0.5, y: 4.5, w: 9, h: 0.4, fontSize: 13, italic: true, color: C.accent1, margin: 0,
  isTextBox: true, objectName: "quick-wins" });
s.addNotes("The governance pack (W04_Governance_Pack.docx) covers how to run this on real data: data dictionary, " +
  "processing rules, taxonomy change process and the monthly re-evaluation.");

(async () => {
  const out = path.join(ROOT, "W04_Findings_Deck.pptx");
  await pres.writeFile({ fileName: out });
  if (process.env.PPTX_SKILL) {
    const { applyTheme } = require(path.join(process.env.PPTX_SKILL, "scripts/apply_theme.js"));
    await applyTheme(out, THEME);
  }
  console.log("wrote", path.relative(ROOT, out));
})();
