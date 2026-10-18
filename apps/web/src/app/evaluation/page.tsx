"use client";

import { useState } from "react";
import Link from "next/link";
import report from "../../../../../reports/evidence/2026-10-18-paired-capture-regression.json";

const labels = { single: "Single image", fixed_capture: "Fixed capture", matched_capture: "Matched budget", adaptive_capture: "Adaptive capture" };
type Strategy = keyof typeof labels;
const percentage = (value: number | null) => value === null ? "Unavailable" : `${(value * 100).toFixed(1)}%`;

export default function EvaluationPage() {
  const [strategy, setStrategy] = useState<Strategy>("adaptive_capture");
  const [filter, setFilter] = useState("all");
  const result = report.results[strategy];
  const cases = result.cases.filter(sample => filter === "all" || (filter === "unresolved" ? sample.decision === "REVIEW" : sample.decision !== sample.expected));
  function download() {
    const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }));
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = "loopsight-synthetic-capture-evaluation.json"; anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 30_000);
  }
  return <main className="mx-auto max-w-6xl space-y-7 px-5 py-10 text-[#e6f0ff]">
    <nav className="flex flex-wrap justify-between gap-4 text-sm">
      <Link href="/" className="text-sky-300 hover:underline">← Back to inspection</Link>
      <button onClick={download} className="rounded-lg border border-sky-400/40 px-4 py-2 text-sky-300">Download full evaluation JSON</button>
    </nav>
    <div className="space-y-3"><p className="text-xs font-mono uppercase tracking-widest text-amber-300">Synthetic regression · Physical validation pending</p>
      <h1 className="text-3xl font-bold">What the current evidence shows</h1>
      <p className="max-w-3xl leading-relaxed text-slate-300">A real OpenCV run over 34 generated primary images in five generator-family groups, with six supplied synthetic companion images. Six ambiguous-label fixtures were excluded. These are software regression checks; they do not establish field accuracy or water safety.</p>
    </div>
    <div role="note" className="rounded-xl border border-amber-400/40 bg-amber-400/10 p-5 leading-relaxed text-amber-100">
      Fixed, matched and adaptive capture tie at 64.7%, requesting six extra images each. Every available pair belongs to an ambiguous first image, so the controls choose the same pairs. This dataset does not demonstrate an adaptive allocation advantage.
    </div>
    <div className="overflow-x-auto rounded-xl border border-slate-700">
      <table className="w-full text-left text-sm"><caption className="p-4 text-left font-semibold">All strategies use the same image policy. REVIEW counts as an abstention.</caption>
        <thead className="bg-slate-900 text-slate-300"><tr>{["Strategy", "Accuracy incl. abstentions", "Coverage", "False-clear rate", "Extra inputs"].map(title => <th key={title} className="p-4">{title}</th>)}</tr></thead>
        <tbody>{(Object.keys(labels) as Strategy[]).map(key => <tr key={key} className="border-t border-slate-700">
          <th scope="row" className="p-4">{labels[key]}</th><td className="p-4">{percentage(report.results[key].accuracy_including_abstentions)}</td>
          <td className="p-4">{percentage(report.results[key].coverage)}</td><td className="p-4">{percentage(report.results[key].false_clear_rate)}</td><td className="p-4">{report.results[key].additional_inputs_requested}</td>
        </tr>)}</tbody>
      </table>
    </div>
    <p className="text-sm leading-relaxed text-slate-400">Zero false clears on this small synthetic fixture set is not a safety guarantee. No physical calibration, statistical significance or independent ground truth is established. The matched budget counts requested image inputs, not compute time or cost. Missing follow-ups are never synthesized.</p>
    <section className="space-y-4" aria-labelledby="case-heading">
      <h2 id="case-heading" className="text-xl font-bold">Inspect individual outcomes</h2>
      <div className="flex flex-wrap gap-5 text-sm">
        <label className="space-x-2">Strategy <select className="rounded border border-slate-600 bg-slate-900 p-2" value={strategy} onChange={event => setStrategy(event.target.value as Strategy)}>{(Object.keys(labels) as Strategy[]).map(key => <option key={key} value={key}>{labels[key]}</option>)}</select></label>
        <label className="space-x-2">Cases <select className="rounded border border-slate-600 bg-slate-900 p-2" value={filter} onChange={event => setFilter(event.target.value)}><option value="all">All</option><option value="unresolved">Unresolved</option><option value="not-correct">Incorrect or abstained</option></select></label>
      </div>
      <p className="text-sm text-slate-400">Showing {cases.length} of {result.samples} cases. Expected labels describe generator intent.</p>
      <div className="overflow-x-auto rounded-xl border border-slate-700"><table className="w-full text-left text-sm"><thead className="bg-slate-900"><tr>{["Case / family", "Expected", "Outcome", "Extra image requested", "Pair status"].map(title => <th key={title} className="p-3">{title}</th>)}</tr></thead>
        <tbody>{cases.map(sample => <tr key={sample.id} className="border-t border-slate-700"><th scope="row" className="p-3 font-normal"><span className="block">{sample.id}</span><span className="text-xs text-slate-400">{sample.group_id}</span></th>
          <td className="p-3">{sample.expected}</td><td className={`p-3 font-semibold ${sample.decision === "REVIEW" ? "text-amber-300" : "text-slate-200"}`}>{sample.decision}</td>
          <td className="p-3">{sample.additional_input_requested ? "Yes" : "No"}</td><td className="p-3">{sample.pair_rejection || (sample.new_capture_used ? "Validated and used" : "No additional capture used")}</td></tr>)}</tbody>
      </table></div>
    </section>
    <section className="space-y-2 rounded-xl bg-slate-900 p-5 text-sm text-slate-300"><h2 className="text-lg font-semibold text-white">Reproduce this report</h2>
      <p>Run the manifest evaluator with seed {report.seed}. The downloaded JSON includes per-case decoded-pixel hashes, the manifest hash, policy thresholds, source-file hashes and runtime versions.</p>
      <pre className="overflow-x-auto py-2 text-xs text-sky-200">python services/inference/scripts/evaluate_captures.py data/synthetic_capture_manifest.json --json /tmp/evaluation.json</pre>
      <p>Recorded runtime: OpenCV {report.runtime.opencv}, Python {report.runtime.python}. Source changes after this report require a rerun before new effectiveness claims.</p>
    </section>
  </main>;
}
