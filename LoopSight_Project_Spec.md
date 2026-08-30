# LoopSight — Full Project Specification
### An Adaptive Visual Reinspection Agent for the OpenCV AI Competition 2026

**Prepared for:** Kathirvel R (kathir-iTech), PSG Institute of Technology and Applied Research
**Target competition:** OpenCV AI Competition 2026, powered by AWS
**Status:** Locked concept, pre-build specification
**Document purpose:** Single source of truth for what to build, why, and how — synthesized from six independent AI research dossiers, cross-checked against the live official competition page and current (30 Aug 2026) documentation, with every stale or unverifiable claim from the source dossiers flagged and corrected rather than silently repeated.

---

## 0. How To Read This Document

This document replaces, not summarizes, the six research dossiers it's built from. Where the dossiers agreed, that consensus is folded in without ceremony. Where they conflicted or were wrong, the conflict is resolved here with a live-checked source, not just repeated. Three corrections worth knowing before reading further, because they change real decisions downstream:

1. **Team size is capped at four, not five.** The official OpenCV competition page (opencv.org, checked 30 Aug 2026) states plainly: *"Register on the official competition Devpost page and participate individually or in a team of no more than four."* One of the six source dossiers flagged this as an unresolved conflict between the overview page and the terms section — it isn't a conflict, four is the number.
2. **`gemini-2.0-flash`, the model most of the source dossiers assumed, was shut down on 1 June 2026.** It will not work. The current model for this project's agent/policy layer is **`gemini-3.7-flash`**, released 13 Aug 2026, which Google specifically positions as its workhorse model for coding and agentic workflows — a better fit for this project's tool-selection loop than the older model would have been anyway.
3. **The default benchmark dataset for this kind of project (MVTec AD) is CC BY-NC-SA 4.0 — non-commercial only.** None of the six dossiers flagged this clearly. It doesn't block the project, but it does mean the dataset can be used for internal validation and never redistributed as part of the public submission — see Section 13.

Every other section follows the same rule: stated plainly, sourced where it matters, and marked **[VERIFY AT BUILD TIME]** wherever something is genuinely time-sensitive (pricing, rate limits, exact package versions) rather than presented as settled when it isn't.

**Revision 2 (post-adversarial-review):** this document was put through a second, deliberately hostile research pass across three independent models, specifically hunting for what was still wrong. It found real problems. The corrected facts are folded into the relevant sections below; the two most important, load-bearing changes are:

1. **The core mechanism is not novel — the novelty claim has been narrowed.** "Adaptive second-look" is an established academic pattern, **active perception / uncertainty-driven sensing** (see Section 8, Section 9). The defensible claim is no longer "we invented this," it's "we measured whether this specific policy beats fixed observation, in this domain, at matched cost" — see Section 14's rebuilt evaluation design.
2. **COOL and the AWS free tier were conflated.** COOL's documented deployment (AWS Marketplace AMI, `m8g.4xlarge`+) and the 750-free-hours offer (`t4g.small`, a different instance family entirely) are not the same thing — see Section 15.

The domain (desktop 3D-printing vs. an alternative with a stronger real-world-impact story) is deliberately left open rather than re-decided unilaterally here — see the note at the end of Section 5. The architecture is built so that decision doesn't block starting the core engine.

---

## 1. Executive Summary

**LoopSight** is a computer-vision quality-inspection system that treats visual uncertainty as something to act on, not something to report and move past. Most inspection tools — and most hackathon entries in this exact category — take one look at an image, run one detector, and output a verdict. LoopSight's first pass is allowed to say *"I don't have enough evidence yet."* When it does, a small, bounded agent decides what additional visual operation would actually resolve the uncertainty — a tighter crop, a different lighting-normalized measurement, a comparison against a reference frame — runs it through OpenCV 5, and only then commits to a decision. The product surfaces that whole chain to the user: **first look → uncertainty → chosen next action → new evidence → final decision**, not a black-box confidence score.

The concrete instantiation this document specifies is **LoopSight for Desktop 3D-Printing** — a print-quality inspector aimed at the maker/hobbyist/small-print-farm community, a deliberate narrowing from the original "generic manufacturing QC" framing that every one of the four non-Quorena research dossiers converged on. The narrowing matters: manufacturing QC in general assumes access to a factory and real defective parts, which a solo second-year student doesn't have. Desktop 3D printing is the same underlying problem — surface defects, geometric deviation, pass/fail inspection under imperfect lighting — but it's a problem Kathir can generate real, first-party data for with a college makerspace printer and a weekend, and it's a problem an enormous, vocal hobbyist community (r/3Dprinting, r/FixMyPrint) already discusses daily. Section 5 lays out this decision and its fallback options in full.

The system is **AI-core, not AI-decorative**: remove OpenCV 5 and there is no product. It satisfies the competition's mandatory requirements (substantive OpenCV 5 image/video analysis, a meaningful AWS component) and is deliberately architected to qualify for both optional $1,000 special awards — **Best Use of COOL** (the workload runs on AWS Graviton, with and without COOL, and the difference is measured, not claimed) and **Agentic Vision** (the system's own OpenCV output is what changes the agent's next tool call — the textbook definition of the award's own criteria).

**Honest risk, stated up front, not buried in Section 20:** the adaptive-reinspection mechanic could turn out to be an impressive demo that doesn't actually beat a simpler fixed two-pass heuristic. That's not a hypothetical worry — it's the specific, falsifiable thing to test in the first real build sprint, before any UI work. Section 14 gives the exact experiment. If it fails, the fallback (same section) is a strong, honest submission built around technical execution and the COOL benchmark rather than a forced agentic story.

## 2. Competition Facts — Verified Against Live Sources (30 Aug 2026)

| Fact | Value | Source |
|---|---|---|
| Official pages | `opencv.org/opencv-ai-competition-2026/` (overview, rules-controlling), `opencv26.devpost.com` (submission platform) | Live-checked |
| Organizers | Sponsor: Amazon Web Services. Administrator: OpenCV Foundation | opencv26.devpost.com |
| Registration / proposal window | Opened 12–13 Aug 2026 | opencv26.devpost.com |
| Build phase | 26 Aug 2026 → 26 Oct 2026, 11:59 p.m. Pacific Time (final submission deadline) | opencv26.devpost.com |
| Team size | **Individual or team of no more than four.** One designated representative receives notices/prizes | opencv.org (live), overrides an unresolved conflict noted in earlier research |
| Total cash prizes | $12,000 — $5,000 / $3,000 / $2,000 for 1st/2nd/3rd, plus two independent $1,000 special awards | opencv26.devpost.com |
| Special awards | **Best Use of COOL** and **Agentic Vision** — each a separate $1,000 award, not mutually exclusive with the main prizes | opencv26.devpost.com |
| Cloud compute grant | 50 teams selected receive a **$150** AWS compute grant (not $200 as one source dossier guessed) via a short proposal: planned OpenCV 5 analysis, planned AWS services, architecture diagram/description, target users, evaluation method, and whether you're pursuing COOL, Agentic Vision, both, or neither, plus a short team bio | opencv26.devpost.com |
| AWS Free Tier new-account credit | New AWS customers: $100 automatic + up to $100 more via eligible onboarding activities, subject to current Free Tier terms and expiration rules | opencv26.devpost.com |
| Mandatory technical requirement | Every entry must use **OpenCV 5 for substantive image or video analysis** and run a **meaningful component on AWS** | opencv26.devpost.com, corroborated by opencv.org |
| Official rubric (100%) | Technical Execution 30% · Innovation 20% · Real-World Impact 20% · User Experience 10% · Documentation/Presentation 10% · Cloud Delivery/Reproducibility/Responsible Operation 10%. Every final entry gets **at least two independent, conflict-free judge scores**, averaged | Official Devpost Rules page (verbatim, confirmed direct from the source), cross-confirmed independently across two of the six research dossiers — the third dossier's rubric (30/25/20/15/10) does **not** match this and should be disregarded |
| Best Use of COOL sub-rubric (100%) | Verified COOL integration on Graviton (or the Arm leg of a hybrid arch) 30% · Architecture/technical quality 25% · Measured performance/cost/reliability/productivity value 20% · Innovation 15% · Reproducibility/demonstration 10% | Official Devpost Rules page |
| Agentic Vision sub-rubric (100%) | Substantive OpenCV5+agent integration 30% · Orchestration/appropriate autonomy 25% · Task effectiveness/evaluation 20% · Failure handling/observability/security/human control 15% · UX/documentation/demo 10% | Official Devpost Rules page |
| Overall-award tie-break | Technical Execution, then Real-World Impact, then a conflict-free additional judge scores all tied entries | Official Devpost Rules page |
| Special-award tie-break | First criterion of that award's own sub-rubric, then the second, then a conflict-free additional judge | Official Devpost Rules page |
| Rejection grounds (Responsible & Ethical Use) | Judges may reject an entry that uses data/models/media without necessary rights or consent; creates unmitigated safety/privacy/security/discrimination/surveillance risk; contains unlawful or abusive content; **misrepresents capabilities, results, benchmarks, or the role of human review**; or violates third-party terms | Official Devpost Rules page — the misrepresentation clause is the direct textual reason Section 14's evaluation has to be run and reported honestly, not asserted |
| Suggested project areas | Active perception for autonomous inspection with agentic orchestration/MCP, physics-informed video prediction, multi-agent visual SLAM, spatial digital twins, plus applications in healthcare, safety, accessibility, agriculture, environmental monitoring, smart cities, education, retail, sports analytics | opencv.org |
| Submission package | Technical report, judge-accessible code, pinned dependencies + setup instructions, architecture diagram, working endpoint or live demo, judge-accessible video ≤5 minutes, evaluation evidence including limitations/failure cases | opencv26.devpost.com |
| IP note — precise scope | You keep full ownership of your entry and underlying IP. What you grant OpenCV/AWS is scoped specifically to **"Submitted Materials"** — the proposal, report, presentation, and video — not your private source code, model weights, datasets, or credentials **merely referenced or demonstrated** in those materials. The broad license only reaches something if that something is itself literally included in what you submit | Official Devpost Rules page, verbatim — this is more favorable than Section 3's earlier framing assumed, and directly informs the recommendation in Section 21 to keep the private repo private and submit only the required report/video/architecture materials |
| Team/eligibility | Participants must be 13+; a minor needs parent/guardian permission. Team members share responsibility for eligibility; one designated representative receives notices and prizes | Official Devpost Rules page |
| India eligibility | Not excluded by published rules, but prize eligibility, tax documentation, and payment terms need checking directly before relying on winning a cash prize | opencv26.devpost.com, Startup Grants India summary |
| Liability cap | Aggregate liability of the organizing parties is capped at USD $100 under the official terms — standard hackathon boilerplate, not something specific to this project | Official Devpost Rules page |

**[VERIFY AT BUILD TIME]:** re-read the live Official Rules page immediately before you start building, not from this table — competition rules pages get amended, and this table is a snapshot.

---

## 3. Why LoopSight, and Not the Other Three

Briefly, for the record — the full comparative reasoning happened in conversation before this document, so this section stays short.

Four ideas came out of six independent research passes: **Quorena Guard** (an anti-cheat agent for your live Knowledge Arena quiz platform), **LoopSight** (this document), **SiteSentinel** (construction-site PPE compliance), and **SpatialGuard AI** (workplace ergonomics monitoring). Quorena Guard was ruled out directly by you — Knowledge Arena is a ~1-year commercial project aimed at school/college clients, and the competition's broad IP-license grant on submitted materials (Section 2) is a real reason to keep that product and this hackathon entry separate. Between the remaining three, LoopSight wins on three counts: its core mechanic (decide what to inspect next, rather than one-shot classify) is the cleanest, least-crowded match to the **Agentic Vision** award's actual wording — "OpenCV output changes a later decision, tool call, or action" is close to a literal description of what LoopSight does, where SiteSentinel's temporal-persistence rule engine and SpatialGuard's threshold-triggered alerts are closer to conventional detect-and-alert systems wearing an agent label. It's also the lighter CV build: LoopSight's core loop needs classical measurements and a small, whitelisted tool set, not a full multi-object tracker with persistent IDs (SiteSentinel) or real-time pose estimation at >24fps in the browser (SpatialGuard). And of the two research dossiers with real technical depth (LoopSight and SiteSentinel), LoopSight's was the more rigorous of the two — it stated its own confidence levels per claim, gave a concrete falsifiable test for its central risk, and didn't oversell.

## 4. Product Thesis

**One sentence:** LoopSight turns uncertain visual inspection into a closed loop — detect, decide what evidence is missing, go get that evidence, then decide — instead of treating one detector pass as the final answer.

**The 2-minute judge story:**
1. A print (or print photo) enters the system.
2. OpenCV 5 detects the part boundary and measures defect-relevant evidence — edge consistency, layer-line regularity, surface texture deviation from a known-good reference.
3. A confidence/evidence-gap rule flags: *"Not enough evidence to call this."*
4. The agent selects one of a small, fixed toolset — `reinspect_crop`, `compare_to_reference_layer`, `measure_edge_continuity`, `track_across_frames` (video mode) — based on what specifically is ambiguous.
5. The second inspection changes the result — not just confirms the first guess with more decimal places.
6. The UI shows the whole trace: **Perception → Agent Decision → Tool Call → New Evidence → Decision**, not a single confidence bar.
7. A benchmark panel shows latency/throughput, and baseline-OpenCV vs. COOL-on-Graviton numbers side by side.
8. The judge sees, concretely, that neither AWS nor OpenCV is decorative.

**The honest novelty claim** — stated exactly this way in the technical report, not oversold: *"The differentiator is an inspection controller that decides what visual evidence to obtain next, rather than treating the first vision pass as the final answer."* Nobody should claim to have invented AI visual inspection. What's being claimed is a specific, narrow, checkable design pattern — active/adaptive reinspection — applied cleanly, measured against a baseline, and shown working.

**What it is not:** not a generic object detector with a UI wrapped around it, not an LLM asked to "look at this image and tell me if it's defective" (that's the thing to specifically avoid — Section 9 explains why), and not a claim to replace human QC judgment. The final PASS/REVIEW/FAIL decision is policy-and-evidence-driven and deterministic; the LLM's only job is choosing which OpenCV tool to run next when the deterministic first pass is genuinely ambiguous.

---

## 5. The Domain Decision: Desktop 3D-Print Quality Inspection

This is the single highest-leverage change this document makes to the original research, so it gets its own section rather than a footnote.

**The problem with "generic manufacturing QC":** every version of this idea across the source research assumed access to real defective manufactured parts — screws, sheet metal, PCBs off a real line. That data doesn't exist for a solo student with no factory relationship, and both the honest source dossiers (LoopSight and SiteSentinel) flagged this as their weakest, least-verifiable section. Building the technical report's "real-world impact" case on a domain you've never actually touched is exactly the kind of thing a skeptical judge — or an honest self-assessment — calls out.

**The fix: narrow to desktop 3D printing, keep the mechanic identical.** The underlying computer-vision problem doesn't change — surface-defect detection, geometric/edge deviation from a known-good reference, decide-what-to-check-next under visual ambiguity — but the domain becomes one you can genuinely generate first-party data for:

- PSG iTech almost certainly has 3D printers in a makerspace, robotics lab, or project lab. If not, desktop FDM printers are common enough among classmates/local maker spaces to borrow for a weekend.
- Common, well-documented print defects are easy to deliberately induce and photograph: **layer shifting**, **stringing**, **warping/lifting corners**, **under-extrusion (gaps/thin walls)**, **blobs/zits**, **elephant's foot**. A few hours printing small test objects with deliberately bad settings produces a real, honestly-labeled dataset — 30–100 images is a realistic, defensible target for a solo build, matching what the source research itself recommended for any version of this idea.
- The target community is large, active, and self-documenting: r/3Dprinting and r/FixMyPrint exist specifically because people can't always tell if a print in progress is failing — a directly citable, real audience, not an invented one.
- It's genuinely demoable live: bring 2–3 physical printed samples to the judges — one good, one or two with real defects — and run the live camera feed in front of them. This is a stronger, more credible demo moment than a slideshow of stock factory photos, and it's something none of the source dossiers could offer because none of them had real physical objects behind the pitch.

**Fallback datasets, non-commercial validation only (see Section 13's licensing note):** MVTec AD's `screw` and `metal_nut` categories are close enough in spirit to benchmark general anomaly-detection performance internally, never redistributed in the public submission. If time allows, a small **PCB or fabric surface-defect dataset** (several exist under more permissive licenses, e.g. Kaggle-hosted PCB defect sets — verify each one's exact license before use) is a reasonable secondary domain to show the system generalizes beyond one object type, which is a genuinely strong Innovation-category argument if there's time for it, and a fine thing to leave as documented future work if there isn't.

**What doesn't change:** the architecture, the agent loop, the AWS deployment, the COOL benchmark plan, and the evaluation methodology in this document all describe "inspect a part for defects" generically — they apply to 3D-print inspection without modification, and they'd apply just as well to a factory part if Kathir ever gets real access to one later. This section only narrows *whose* defects get inspected in the demo, not how the system works.

**Revision 2 note — domain is genuinely still open, and deliberately not re-decided here.** The adversarial research pass surfaced two things worth being honest about. First, desktop-FDM defect detection turns out not to be underexplored the way this section originally implied — there's real open-source prior art (3DPrintSaviour, `failure_detection_for_3d_printing`, PrintGuard/duetPrintGuard) and real academic prior art going back to 2017 (Holzmond & Li's in-situ FFF monitoring, Jin et al.'s 2019 closed-loop adaptive correction system, Petsiuk & Pearce's 2022 training-free reference-comparison approach) — see Section 8. Second, three independent research passes each proposed a *different* alternative domain with a stronger real-world-impact story (solar-panel inspection, composite/filament-winding inspection, PCB solder-joint inspection), and none of them agree with each other, which means this isn't a settled call research can make — it depends on what Kathir can actually get physical access to.

Rather than guess, the system is built domain-agnostic from the start: the `/inspect` endpoint's `inspection_profile` field (Section 12) is what selects the reference images, defect vocabulary, and measurement thresholds for a given object type. The core engine — first-pass measurement, evidence-gap scoring, the agent's tool selection, the deterministic final policy — doesn't change based on what's being inspected. `fdm_print_surface_v1` is the default profile built and tested first, purely because it's the domain already scoped end-to-end in this document; a `pcb_solder_v1` or other profile is a data-and-config swap on top of the same engine, not a rewrite, if a stronger domain becomes accessible later. Section 18's build plan starts with the profile-agnostic core precisely so this choice doesn't block starting.

## 6. Problem Statement

**Precise problem:** Desktop 3D-printing users — hobbyists, student makers, and small print-farm operators — routinely can't tell, mid-print or from a single finished-part photo, whether a visible irregularity is a real defect that will ruin the part or a harmless artifact of lighting, filament color, or camera angle, and existing "AI print monitor" tools give a single confidence score with no way to interrogate *why*.

**Who / evidence:** Anyone running FDM printers without professional QC tooling — the exact population active on r/3Dprinting and r/FixMyPrint, both large, long-running communities built around this specific uncertainty ("is this normal or should I stop the print?"). Severity is moderate-to-high per failed print (wasted filament, wasted print time — often multi-hour), not life-safety-critical, which is itself a feature for a hackathon-scale project: it's real and demoable without inheriting the high-stakes disclaimers a safety-monitoring pitch would require.

**Current workaround:** Visual gut-check by the operator, sometimes assisted by single-shot "AI failure detection" plugins (Obico/Spaghetti Detective and similar) that flag spaghetti-style catastrophic failure but don't reason about ambiguous, partial, or early-stage defects — see Section 8.

**Why now:** OpenCV 5's rewritten DNN engine and broadened ONNX coverage make running a real classical-plus-lightweight-model inspection pipeline on CPU-only, free-tier compute genuinely practical — the same "why now" that applies to this whole competition category, not a forced justification specific to this idea.

**Falsifiable test:** Print three identical test objects — one clean, two with deliberately induced different defect types — and confirm the system (a) correctly passes the clean one without triggering a needless reinspection, (b) correctly escalates the ambiguous cases through a second inspection pass, and (c) reaches the right final verdict on all three. This is a test that can be run in an afternoon, not a hypothetical.

**What a domain expert would say:** A print-farm operator or makerspace lab tech would recognize the underlying problem instantly (it's a constant low-grade annoyance in that world) and would likely push back on any claim of catching *every* failure type — the honest scope here is a defined, disclosed set of common defect classes, not universal failure detection.

---

## 7. Target Users & Personas

**Primary persona — "The Weekend Maker."** A student or hobbyist running one or two desktop FDM printers, checking on prints periodically rather than watching continuously, wanting a plain answer ("is this fine or should I stop it") rather than a raw confidence number they have to interpret themselves.

**Secondary persona — "The Small Print-Farm Operator."** Runs several printers simultaneously (a real, growing small-business category — print-on-demand shops, campus makerspace attendants managing a bank of printers for student projects). Cares about catching failures early enough to stop a print before it wastes hours of filament and machine time across multiple jobs at once, and wants a review queue, not just single-print detection.

**What earns trust:** Deterministic, inspectable reasoning over a black-box score — this user group is technical enough to want to understand *why* the system flagged something, not just be told a percentage. This directly motivates the evidence-trace UI (Section 9) over a plain confidence bar.

**Realistic device/context:** A phone or webcam pointed at the print bed, or a periodic photo upload — not a dedicated industrial camera rig. Setup friction must be near zero: point a camera, get an answer, no calibration ritual.

**What "I'd pay for this" looks like:** A print-farm operator saying they'd pay per-camera/month for a review dashboard across multiple simultaneous prints — a real, if modest, willingness-to-pay signal distinct from a single hobbyist's one-off use.

**Realistic first negative reaction:** *"Does this actually catch more than the free plugins already do?"* — the honest answer has to be the evaluation result from Section 14, not a marketing claim.

---

## 8. Competitive Landscape

| Existing option | Core mechanic | Gap |
|---|---|---|
| **Obico (formerly The Spaghetti Detective)** | Single-pass CV model watching for catastrophic "spaghetti" failure, cloud or self-hosted | Built for one failure mode (total print collapse); doesn't reason about ambiguous partial defects or explain its confidence |
| **PrusaSlicer / OctoPrint plugins (various)** | Rule-based or simple-model print-monitoring add-ons | Mostly single-signal, no adaptive re-check, no evidence trace |
| **Generic industrial QC vision platforms** (Landing AI, Instrumental) | Enterprise defect detection for real factory lines | Wrong market entirely — enterprise sales cycle, real hardware installs, irrelevant to a desktop hobbyist |
| **Academic anomaly-detection research** (the MVTec-benchmark literature broadly) | State-of-the-art unsupervised anomaly detection methods | Strong on raw detection accuracy benchmarks; none of it is packaged as an end-user tool with an adaptive, explainable second-look step |
| **3DPrintSaviour** (open source) | Compares successive Octolapse layer images via NRMSE to flag detachment/breakage/filament-runout, can pause the printer through OctoPrint | Single fixed comparison per layer, no uncertainty-triggered escalation, no evidence trace shown to the user |
| **`failure_detection_for_3d_printing`** (open source, MIT) | Image matching between slicer-expected and actual imagery, object tracking, spaghetti detection | Same single-pass shape as above; classical CV, not agentic |
| **PrintGuard / duetPrintGuard** (open source) | On-device fault detection (ShuffleNetV2-class model or frame-persistence rules), integrates with printer control to pause/cancel | The most advanced of the open-source options — this is the bar to differentiate against, not a strawman |

**Revision 2 correction — the honest novelty claim is narrower than the first draft of this section implied.** An adversarial second research pass found that "camera + CV/ML detects 3D-print defects" is an already-populated space, not white space: the open-source projects above already do real work here, and academic prior art goes back further than a hackathon timeline would suggest — Holzmond & Li (2017) did in-situ FFF monitoring comparing printed geometry against the CAD model; Jin, Zhang & Gu (2019) built a CNN-based system with a **closed feedback loop that adaptively modified print parameters**, reporting >98% quality-status accuracy; Petsiuk & Pearce (2022) showed a training-free, classical HOG-based reference-comparison system worked without any learned model at all. None of that makes LoopSight pointless — it makes the honest claim narrower. See Section 9 for the corrected framing.

**AI-core vs. AI-decorative:** AI-core. Remove OpenCV 5 and there is no defect signal at all — the product collapses to a person staring at the print bed, exactly the status quo it replaces.

**Prior-art paragraph, ready to paste into the technical report:** *"Existing print-monitoring tools — from single-signal OctoPrint plugins to on-device systems like PrintGuard — reliably catch failures once enough visual evidence has accumulated, using a fixed observation budget per check. Academic work (Holzmond & Li, 2017; Jin et al., 2019; Petsiuk & Pearce, 2022) has already explored both learned and training-free defect detection for FFF printing, including closed-loop adaptive correction. LoopSight does not claim to be the first system to detect print defects with computer vision — it isolates and tests one narrower question: does an uncertainty-triggered decision about when to take a second, materially different observation improve on a fixed observation budget, measured directly against that baseline rather than assumed."*

**"Couldn't someone just prompt Gemini/ChatGPT with the image and ask if it's defective?"** This is the single sharpest skeptical-judge question and deserves a direct, honest answer in the report: yes, for a single glance, and it would probably do a passable job on obvious cases. What it wouldn't do is a **bounded, deterministic, reproducible** second look driven by a specific evidence gap — a raw vision-LLM call is exactly the "confidence theater" this project is designed to avoid, per Section 9's design constraint that the LLM only picks *which OpenCV tool* to run next, never renders the actual pass/fail judgment itself.

## 9. Core Mechanic — Uncertainty-Triggered Active Perception

**Revision 2 renaming:** this section was originally titled "The Adaptive Reinspection Loop." The adversarial research pass confirmed the mechanism has an established academic name — **active perception** (or, more specifically, **uncertainty-driven sensing**; **next-best-view** applies only if the physical viewpoint actually changes) — and that presenting it as an unnamed invention would read as either naive or evasive to a technical judge. The mechanism itself is unchanged; only the claim about it is corrected. See Section 8 for the prior art this sits inside.

**Design constraint, stated once and enforced everywhere else in this document:** OpenCV 5 produces evidence; a small deterministic policy plus a bounded agent decides what to do with it; the final PASS/REVIEW/FAIL decision is never a free-form LLM judgment call. This is what keeps the system defensible as "AI-core, not a wrapper" to a technical judge, and it's what keeps a false confidence signal from ever reaching a user unchecked.

**Step by step:**

1. **First pass (deterministic, OpenCV 5 only):** Given an image or video frame, detect the part boundary and reference orientation, then compute a small set of concrete measurements — edge continuity along expected boundaries, local texture deviation from a stored known-good reference of the same object/settings, geometric deviation (warping, layer alignment) via contour analysis. No neural model is required for v1; classical OpenCV operations (edge detection, contour analysis, structural similarity against a reference) are sufficient and keep the "substantive OpenCV 5 use" claim unambiguous.
2. **Evidence-gap scoring:** A deterministic rule (not a model) converts those measurements into one of three states — `CONFIDENT_PASS`, `CONFIDENT_FAIL`, or `UNCERTAIN` — plus, when uncertain, a structured `evidence_gap` field naming *what specifically* is ambiguous (e.g., `"low local contrast — cannot confirm edge deviation"`).
3. **Agent tool selection (only reached when `UNCERTAIN`):** `gemini-3.7-flash`, given the structured evidence-gap output (not the raw image) and a fixed, whitelisted tool list, picks one tool: `reinspect_roi` (re-crop and re-measure a specific region at higher resolution), `compare_to_reference` (structural-similarity comparison against the known-good reference), `measure_edge_continuity` (a focused geometric pass), or `track_across_frames` (video mode only — check whether the anomaly persists or was a transient lighting/motion artifact). The model returns a `reason_code`, not free-text reasoning — a controlled categorical field, not something to parse loosely.
4. **Second pass:** The chosen tool runs through OpenCV 5 again, over the same or a refined crop of the same image.
5. **Final decision:** A second deterministic policy pass combines both rounds of evidence into `PASS`, `REVIEW`, or `FAIL`, with `human_approval_required: true` whenever the result is anything but a confident pass. `REVIEW` is a legitimate, expected outcome, not a failure of the system — a print-farm operator glancing at a `REVIEW` queue is the intended steady-state, not an edge case to eliminate.

**Minimum viable core loop, nothing else required for v1:** one image in → one first-pass measurement → one evidence-gap check → one bounded agent tool call → one second measurement → one deterministic verdict. Everything past this (video mode, multi-object batches, the review dashboard) is additive scope, explicitly ordered in Section 18's build plan.

**What breaks it, and the honest limitation to disclose rather than let a judge discover live:** a single, unusually clean "lucky" first pass that happens to nail an ambiguous case without ever exercising the second-pass loop at all — rehearse the demo with a genuinely ambiguous case, not only the clean pass/fail examples, so the judge actually sees the loop fire.

**Revision 2 addition — the second observation must be materially different, or the whole claim collapses.** This is the sharpest single correction from the adversarial pass. If `reinspect_roi` just re-reads the same webcam frame and re-crops it in software, a judge can reasonably ask what actually changed — and there's a real, specific engineering failure mode that makes this worse than a framing problem: **webcam driver buffering.** A `cv2.VideoCapture.read()` call issued immediately after an expensive first-pass analysis can return a stale buffered frame rather than the true current frame, so the "second look" silently inspects the same moment in time twice. The loop looks like it fired; it didn't actually gather new evidence. The fix is architectural, not cosmetic:

- A dedicated capture thread that continuously drains the camera buffer, so `read()` always returns the most recent frame, not a queued one.
- Every frame tagged with a sequence ID and a capture timestamp.
- The evidence-trace UI displays both timestamps (`LOOK 1: 12:41:07.183 · frame #1842`, `LOOK 2: 12:41:07.431 · frame #1849`) so the second observation is auditably different, not just claimed to be.
- Where possible, the second look should change something real about the observation — a tighter crop at higher effective resolution, a different exposure/contrast normalization, or (if a second camera or a repositionable one is available) an actual angle change — not merely a re-read of the same framing.

## 10. System Architecture

```text
                    ┌──────────────────────────┐
                    │   Next.js 16 UI (Vercel)  │
                    │  upload / live camera /   │
                    │  evidence-trace viewer    │
                    └────────────┬─────────────┘
                                 │ POST /inspect
                                 ▼
                    ┌──────────────────────────┐
                    │   AWS API Gateway (HTTP)  │
                    │   short-lived signed URLs │
                    └────────────┬─────────────┘
                                 ▼
               ┌─────────────────────────────────┐
               │ AWS Graviton (ARM64) CV Runtime   │
               │ Docker container: FastAPI +      │
               │ OpenCV 5 (+ COOL where applicable)│
               │                                   │
               │ 1. preprocess / decode            │
               │ 2. detect part + reference align  │
               │ 3. first-pass measurements         │
               │ 4. evidence-gap scoring            │
               └──────────────┬───────────────────┘
                              │ structured findings (JSON)
                              ▼
                    ┌───────────────────────┐
                    │  Agent / Policy Layer  │
                    │  gemini-3.7-flash      │
                    │  tool selection only   │
                    └──────────┬────────────┘
                               │ {tool, arguments, reason_code}
               ┌───────────────┼─────────────────┐
               ▼               ▼                 ▼
        ┌────────────┐  ┌────────────┐   ┌──────────────┐
        │ ROI refine │  │ Reference  │   │ Temporal     │
        │ (OpenCV)   │  │ compare    │   │ track        │
        │            │  │ (OpenCV)   │   │ (OpenCV)     │
        └─────┬──────┘  └─────┬──────┘   └──────┬───────┘
              └───────────────┼─────────────────┘
                              ▼
                    ┌───────────────────────┐
                    │  Deterministic final   │
                    │  decision policy       │
                    └──────────┬────────────┘
                               ▼
               PASS / REVIEW / FAIL + full evidence trace
                               │
                     ┌─────────┴─────────┐
                     ▼                   ▼
             S3 (evidence images   DynamoDB (job +
             + result artifact)    incident metadata)
                     │
                     ▼
             CloudWatch (logs, latency, COOL-vs-baseline metrics)
```

**Why Graviton + a container, not plain Lambda:** OpenCV 5 with COOL is specifically an ARM64/Graviton-optimized workload — a container on Graviton (EC2 or Fargate, both cover-able inside AWS Free Tier hours at this project's scale) makes both the "meaningful AWS component" requirement and the COOL benchmark straightforward. Lambda remains a fine choice for the thin API-orchestration layer around it, but the actual OpenCV+COOL inference workload belongs on Graviton, not squeezed into a Lambda package with the cold-start and package-size problems that come with bundling a native-compiled CV library there.

**The "heart" endpoint:**

```text
POST /inspect
in:  { media_url, inspection_profile, max_agent_steps }
out: { job_id }

GET /jobs/{job_id}
out: { status, first_pass, agent_calls[], final_pass, decision, evidence_trace, timing }
```

**State:** No user accounts needed for v1 — a job is identified by its `job_id`, results persist in DynamoDB, and evidence images persist in S3 with a short lifecycle-delete policy. Session-only mode is enough for early development; persistent storage is needed for the reproducible-deployment requirement in the submission checklist.

**Auth:** None for the judge-accessible demo endpoint — protect it instead with a single demo token and short-lived signed S3 URLs, exactly as one of the source dossiers recommended, rather than standing up a real auth system that adds risk without adding anything judges score on.

**Mock mode:** Build this first, before the real Graviton container exists — wire the UI and evidence-trace viewer against a hand-written mocked `/inspect` response. This is standard hackathon risk-reduction and lets UI work start in parallel with the CV pipeline.

**Fallback if AWS is unreachable mid-demo:** a small set of pre-computed "golden" results keyed to the exact rehearsed demo objects, so a live AWS hiccup in front of judges never fully breaks the demo — this is not optional polish, build it as a real fallback path, not an afterthought.

**Single point of failure:** the AWS inspection endpoint. Mitigated by the golden-result fallback above and by making sure a single failed inspection never crashes the UI, only shows a clear "inspection failed, try again" state.

## 11. Technology Stack

| Layer | Choice | Notes / **[VERIFY AT BUILD TIME]** |
|---|---|---|
| Frontend framework | Next.js (App Router), TypeScript, Tailwind CSS | Confirm the current stable Next.js release and scaffold command at build time — check for any security releases the way you'd check any dependency before starting |
| Frontend hosting | Vercel Hobby (free tier) | Matches your existing setup for Knowledge Arena; no card required |
| UI components | shadcn/ui + Tailwind | For the evidence-trace viewer and job dashboard |
| CV runtime language | Python | `opencv-python-headless` — the server-safe build with no GUI dependencies. **[VERIFY]** exact current wheel version at install time |
| CV library | **OpenCV 5** | Mandatory per competition rules. Record `cv2.__version__` in the submitted report as required evidence |
| Optimization path | **COOL** (Cloud-Optimized OpenCV Library) on **AWS Graviton (ARM64)** | **Revision 2 correction:** not a `pip install`. Current distribution is an **AWS Marketplace AMI** — subscribe, launch a Graviton EC2 instance from the AMI (Graviton4 listing recommends `m8g.4xlarge` or larger; `c8g`/`r8g` also compatible), then activate the prebuilt environment: `source /opt/cool/venvs/python_3.12/bin/activate`. Verify with `python3 -c "import cv2; print(cv2.__version__)"`. Realistic expected speedup over baseline OpenCV on this pipeline's scale of workload: **modest, ~20–30%** (AWS's own representative benchmark: 1.2→1.6 fps) — treat as a hypothesis to measure in Experiment D, not a promised win |
| Inference container host | AWS Graviton (EC2, ARM64), launched from the COOL AMI directly rather than a custom Docker base image | Building a custom image on top of a non-AMI base risks missing the `/opt/cool` paths — start from the documented AMI, containerize later only if needed |
| API orchestration | AWS API Gateway (HTTP API) + a thin Lambda or FastAPI layer | Keep this layer thin — it routes and validates, it doesn't run the heavy CV workload |
| Agent / policy model | **`gemini-3.7-flash`** (default; benchmark a Lite-tier model before locking) | Current (13 Aug 2026) GA model, positioned by Google specifically for coding/agentic workflows — confirmed current as of this research pass, though one of three Phase-2 research passes incorrectly claimed it wasn't GA yet, which is itself a reason to re-verify directly rather than trust any single source. **Revision 2:** for this project's narrow tool-selection task (pick 1 of 4 fixed options), a Flash-Lite-tier model is very plausibly sufficient and meaningfully cheaper/faster — the three research passes couldn't agree on which one is current (`gemini-3.1-flash-lite` vs. `gemini-2.5-flash-lite` were both named), which is itself the signal to check Google AI Studio directly at build time rather than trust a name from this document. Benchmark 3–5 models on ~100 scripted tool-selection cases (correct tool / latency / malformed-JSON rate / cost) before committing. **[VERIFY]** current free-tier RPM/RPD — Google's own docs say these are project/tier-specific and not a stable public constant, so do not hardcode a number anywhere in the report |
| Structured output | Gemini's JSON-mode / `responseSchema`, validated with Zod on receipt | Enforces the `{tool, arguments, reason_code}` contract from Section 9 |
| Object storage | AWS S3 | Evidence images + result artifacts; short lifecycle-delete policy |
| Metadata / job state | AWS DynamoDB | Job records, incident metadata |
| Observability | AWS CloudWatch | Logs, latency measurements, the baseline-vs-COOL benchmark numbers |
| CI | GitHub Actions | Free tier, effectively unlimited for a public repo |
| Demo recording | OBS Studio | Free, no watermark, for the required ≤5-minute submission video |

**Deliberately excluded from v1** — not because they're bad ideas, but because they don't move the score and do add real risk in a solo, time-boxed build: user accounts/login, billing, multi-tenancy, a general-purpose chatbot interface, RAG over a knowledge base, a native mobile app, any custom foundation-model training, a full 3D digital-twin visualization, and any real manufacturing-line (PLC/MES) integration. If any of these feel tempting mid-build, that's the scope-creep signal Section 20 warns about, not a good sign.

## 12. Data Contracts

**Input to `/inspect`:**
```json
{
  "media_url": "s3://loopsight-media/sample-042.jpg",
  "inspection_profile": "fdm_print_surface_v1",
  "max_agent_steps": 2
}
```

**First-pass output (from the OpenCV 5 stage, before any agent involvement):**
```json
{
  "status": "UNCERTAIN",
  "regions": [
    {
      "x": 120, "y": 90, "w": 220, "h": 180,
      "evidence": {
        "edge_continuity": 0.81,
        "reference_similarity": 0.64,
        "layer_alignment_deviation": 0.48
      }
    }
  ],
  "evidence_gap": ["low local contrast — cannot confirm edge deviation"],
  "allowed_tools": ["reinspect_roi", "compare_to_reference", "measure_edge_continuity", "track_across_frames"]
}
```

**Agent output (`gemini-3.7-flash`, structured, tool selection only):**
```json
{
  "tool": "reinspect_roi",
  "arguments": { "region_id": 0, "scale": 2.0 },
  "reason_code": "INSUFFICIENT_LOCAL_CONTRAST"
}
```
The model's free-text reasoning, if any, is never surfaced to the product logic — `reason_code` is a small, fixed enum, checked against the whitelist before any tool actually runs. This is a real safety property, not just tidiness: it means a prompt-injected or malformed model response can't cause an arbitrary or unbounded action.

**Final output:**
```json
{
  "decision": "REVIEW",
  "confidence_band": "medium",
  "evidence_changed": true,
  "human_approval_required": true,
  "measurements": {
    "first_pass_latency_ms": 412,
    "second_pass_latency_ms": 233,
    "total_latency_ms": 1180
  }
}
```

---

## 13. Data & Model Strategy

**Primary dataset: self-captured.** Print 6–10 small test objects (a benchy, a calibration cube, a few simple brackets) under normal settings, then deliberately induce 3–6 distinct defect types across repeat prints — layer shifting, stringing, warping, under-extrusion, blobbing, elephant's foot. Photograph each from a consistent angle under a couple of different lighting conditions. This realistically yields 30–100 labeled images, which matches what every source dossier independently recommended as a realistic solo-builder target, and — critically — it's data Kathir actually owns and can freely license, publish, and redistribute as part of the submission with zero legal question marks.

**Secondary/benchmark dataset — MVTec AD, non-commercial internal use only.** MVTec AD (and the related MVTec AD 2, LOCO, 3D-AD, ITODD datasets) are released under **CC BY-NC-SA 4.0** — explicitly non-commercial. This is a genuine licensing point the source research understated. The safe pattern: use MVTec's `screw` or `metal_nut` categories, if at all, purely to sanity-check the general anomaly-detection approach during development, cite it properly in the report, and **never redistribute the dataset itself** as part of the public submission. Given the competition's own broad IP-license grant on submitted materials (Section 2), the cleanest path is to lean on the self-captured 3D-print dataset for anything that ships in the public repo, and mention MVTec only as a citation in the evaluation methodology, not as bundled data.

**Model strategy:** No trained neural model is required for v1 — classical OpenCV operations (edge detection, contour analysis, structural similarity) are the whole first-pass pipeline, which keeps "substantive OpenCV 5 use" unambiguous and sidesteps training-data questions entirely. If time allows past the MVP cut line (Section 18), a small ONNX-based defect classifier trained on the self-captured set is a legitimate stretch goal, not a v1 requirement.

**`gemini-3.7-flash` role, restated for emphasis:** tool selection only, never the visual judgment itself. This is both the honest technical design and the strongest defense against the "isn't this just an LLM wrapper" criticism a technical judge is likely to raise.

---

## 14. Evaluation Plan — What Actually Proves This Works

This is the section that resolves the project's single biggest honest risk (Section 1): **does adaptive reinspection actually beat a fixed second-pass heuristic, or does it just look impressive?**

**Experiment A — Baseline.** Run the self-captured test set through a single-pass classifier only (no adaptive loop). Record precision, recall, and false-alert rate.

**Experiment B — Fixed second pass.** Same test set, but every `UNCERTAIN` first-pass result automatically gets one fixed, non-adaptive second pass (e.g., always re-crop tighter, regardless of what's actually ambiguous). Record the same metrics.

**Experiment C — Adaptive (LoopSight's actual mechanic).** Same test set, agent-selected second pass based on the specific evidence gap. Record the same metrics.

**The honest gate:** if Experiment C doesn't measurably beat Experiment B, the adaptive-agent story isn't earning its complexity, and the deciding factor from the source research applies directly: keep the same product shell, drop the LLM-driven tool selection, replace it with the best-performing deterministic policy from Experiment B, and redirect the pitch toward technical execution, the COOL benchmark, and the evidence-trace UX instead of forcing an agentic narrative that the numbers don't support. This is a real, respectable fallback position, not a failure state — it's still a stronger, more honest submission than most competitors' one-pass detectors.

**Revision 2 addition — Experiment B alone is not a strong enough control, and this was the single most-repeated correction across all three adversarial research passes.** Experiment B tells you whether a second look helps at all. It does not tell you whether *choosing when to look again* is worth anything over *always looking again* — a simpler, cheaper design that needs no agent at all. Add:

**Experiment B2 — Matched observation budget.** Compare LoopSight's adaptive policy (1 look most of the time, 2 when triggered) against a fixed-repeat baseline that always takes the same *average* number of observations LoopSight actually used — not always 2, but whatever LoopSight's real trigger rate works out to. This is the fair fight: same total sensing cost, different policy for spending it.

**The number that actually settles the question:**

```
conditional_benefit = P(correct | 2nd look, was UNCERTAIN) − P(correct | 1st look only, was UNCERTAIN)
```

If this is close to zero, the adaptive mechanism isn't earning its complexity even if Experiment C's raw accuracy looks fine — a fixed policy at the same average cost would do just as well. Report `trigger_rate`, `resolution_rate` (how often the 2nd look actually changes the verdict), `false_trigger_rate`, and `missed_trigger_rate` alongside accuracy, not just accuracy alone.

**Experiment D — COOL vs. baseline OpenCV on Graviton.** Same inference workload, measured with and without COOL, on the same Graviton instance type. This is the literal evidence needed for the Best Use of COOL award and for the rubric's Cloud Delivery category.

**Experiment E — Robustness.** Deliberately include 2–3 genuinely ambiguous or adversarial cases in the test set — poor lighting, a partially occluded print, a borderline defect a reasonable human would also hesitate on — and report how the system handles them, including cases where it should end in `REVIEW` rather than a confident call. A system that only ever demos clean pass/fail cases hasn't actually been tested.

## 15. AWS Architecture, Cost & Free-Tier Plan

**Revision 2 correction — the 750 free hours and COOL's recommended instance are two different instance families, not one figure.** The original table below implied the free tier directly covered the COOL deployment. It doesn't, and this was independently confirmed by all three Phase-2 research passes:

- The **750 free hours/month** offer is `t4g.small` — a Graviton2, burstable, small instance, confirmed live through 31 Dec 2026.
- COOL's documented Graviton4 deployment recommends `m8g.4xlarge` **or larger** — a completely different, non-free instance family.
- Practical read: the 750 free hours are genuinely useful for the thin orchestration/testing side of the project, and for running the classical-CV pipeline *without* COOL at small scale — but the actual COOL-vs-baseline benchmark (Experiment D) should be budgeted as a real, if modest, paid cost: launch the Graviton4 instance only for the benchmarking window, capture the numbers, then stop it. This is exactly what the billing alarm below exists to guard.

| Component | Free-tier basis | Real current limit | Cost-control note |
|---|---|---|---|
| Inference compute (dev/testing, no COOL) | AWS Graviton EC2 `t4g.small` | 750 always-free hours/month, confirmed live through 31 Dec 2026 | Fine for developing and testing the classical-CV pipeline pre-COOL; stop when idle |
| Inference compute (COOL benchmark, Experiment D) | AWS Graviton4 `m8g.4xlarge`+ via the COOL Marketplace AMI | **Not free-tier eligible** — budget this as a real, small, time-boxed cost | Launch only for the benchmarking window; capture the numbers; terminate immediately after — do not leave it running |
| Orchestration | AWS Lambda | 1M invocations/month + 400,000 GB-seconds, always-free | Thin layer only — the heavy CV workload stays on Graviton, not here |
| Object storage | AWS S3 | 5GB standard storage, always-free | Lifecycle-delete evidence images and job artifacts after the demo period |
| Metadata | AWS DynamoDB | 25GB storage + a modest always-free read/write allowance | Comfortably covers a hackathon-scale job count |
| CDN (if needed) | AWS CloudFront | 1TB out + 10M requests/month, always-free | Only needed if serving evidence images publicly at volume |
| New-account credit | AWS Free Plan | $100 automatic + up to $100 more via onboarding activities, per the competition's own page | Confirm Kathir's AWS account creation date — Free Plan accounts (created after 15 Jul 2025) auto-close after 6 months or when the credit is exhausted |
| Competition grant | $150 compute grant, 50 teams selected | Apply via the short proposal described in Section 2 — worth doing regardless of odds, since the proposal itself doubles as a forcing function to finalize the architecture early | Apply early in the build phase, not near the deadline |
| Frontend hosting | Vercel Hobby | Free, no card | Existing pattern from Knowledge Arena |
| CI | GitHub Actions | 2,000 min/month, effectively unlimited for a public repo | — |
| Demo video | OBS Studio | Free, no watermark | — |

**Real risk if a free-tier limit is hit live:** at this project's realistic demo-day traffic (a handful of judges/testers), the actual risk isn't hitting a hard rate limit — it's a Graviton cold-start delay if the instance was stopped to save cost. Keep it warmed up for a scheduled window around the actual demo, not running continuously for weeks.

**Billing hygiene, non-negotiable regardless of hackathon deadline pressure:** set a CloudWatch billing alarm on day one, before writing any inference code. This is a five-minute task that prevents the one genuinely bad outcome (an unexpected AWS bill) that has nothing to do with the competition itself.

---

## 16. COOL & Agentic Vision Award Alignment

**Best Use of COOL** requires verified COOL integration on AWS Graviton (or a documented ARM hybrid architecture), plus measured performance/cost/reliability value — not just a claim that COOL was used. Experiment D (Section 14) is the literal evidence: run the identical inference workload with and without COOL on the same Graviton instance, report the delta in latency and/or throughput, and include that comparison table in both the technical report and the demo video. Treat the COOL benchmark as a real design decision the product depends on, not a checkbox added after the fact — a real optimization measured honestly is a stronger claim than an unmeasured "we used COOL."

**Agentic Vision** requires substantive OpenCV 5 combined with genuine agent integration — orchestration, evaluation, failure handling, observability, security, and human control, with OpenCV's own output changing what the agent does next. LoopSight's core mechanic (Section 9) is a close-to-literal match: the first-pass OpenCV output is exactly what determines the agent's tool call, the tool call is bounded to a small whitelisted set (a real security/safety property, not incidental), the second-pass evidence changes the final decision, and `human_approval_required` is a real, enforced gate, not a documentation-only promise. The evidence-trace UI (Perception → Agent Decision → Tool Call → New Evidence → Decision) is designed specifically to make this loop visible and auditable to a judge in under two minutes, which is exactly what the award's evaluation criteria (evaluation, observability) are asking to see.

**Important:** both awards should be *consequences of how the product is actually designed*, not features bolted on to chase a checkbox. A judge evaluating "Best Use of COOL" or "Agentic Vision" is specifically primed to notice the difference between a real design decision and a decorative one — this is the single clearest lesson pulled from the strongest of the six source dossiers, and it's also explicit in the rules: *"COOL or agentic methods are not required for the Overall Awards. When present, judges will credit them within the applicable overall criteria only to the extent that they improve the project."* In other words, a forced, unhelpful use of either would not just fail to win the special award — it would actively count against the Overall score too.

**Mapped directly against the official sub-rubrics (Section 2):**

| Best Use of COOL (weight) | LoopSight evidence |
|---|---|
| Verified COOL integration (30%) | Experiment D's side-by-side benchmark, run on the actual Graviton deployment, not simulated |
| Architecture/technical quality (25%) | Section 10's architecture, specifically the choice of Graviton container over Lambda for the heavy CV workload |
| Measured value (20%) | Real latency/throughput numbers, not an estimate |
| Innovation (15%) | Secondary to the Agentic Vision award's innovation story, but the same adaptive-reinspection mechanic still applies |
| Reproducibility/demo (10%) | The fresh-deployment test in Phase 8, and the pinned setup instructions in the repo |

| Agentic Vision (weight) | LoopSight evidence |
|---|---|
| Substantive OpenCV5+agent integration (30%) | Section 9's loop — OpenCV output is literally what the agent's tool call depends on |
| Orchestration/appropriate autonomy (25%) | The bounded, whitelisted tool set (Section 26's code enforces this twice), `max_agent_steps` cap |
| Task effectiveness/evaluation (20%) | Experiments A–C directly measure whether the agent's involvement improves the outcome |
| Failure handling/observability/security/human control (15%) | `human_approval_required` gate, CloudWatch observability, the golden-result fallback path |
| UX/documentation/demo (10%) | The evidence-trace viewer, built specifically to make this loop legible in the ≤5-minute video |

---

## 17. Judging Criteria Alignment

| Criterion (weight) | What LoopSight shows |
|---|---|
| **Technical Execution (30%)** | A working OpenCV 5 pipeline (classical CV + optional lightweight model), real precision/recall numbers from Section 14's experiments, pinned dependencies, a working AWS deployment |
| **Innovation (20%)** | The adaptive-reinspection mechanic itself — explicitly contrasted against the single-pass status quo (Section 8) — plus, if time allows, the domain-generalization stretch goal (a second object category beyond 3D prints) |
| **Real-World Impact (20%)** | A real, named, active user community (r/3Dprinting, r/FixMyPrint), a falsifiable test with real physical objects, an honest six-month impact metric: *number of print-hours saved by catching a defect before print completion* |
| **User Experience (10%)** | The evidence-trace viewer — a plain-language "why" for every REVIEW result, not a raw confidence number; near-zero setup friction (point a camera, get an answer) |
| **Documentation/Presentation (10%)** | This document's structure, condensed into the required technical report: architecture diagram, pinned setup instructions, an honest limitations/failure-cases section |
| **Cloud Delivery/Reproducibility/Responsible Operation (10%)** | CloudWatch observability, a stated IAM least-privilege approach, the COOL-vs-baseline benchmark as evidence of deliberate, measured cloud usage rather than default settings left untouched |

**Currently weakest category, honestly:** Innovation, the same way it was for every idea in the source research — the underlying category (visual defect inspection) is well-trodden. The mitigating factor is that the *specific* mechanic (adaptive evidence-gathering, not one-shot classification) genuinely isn't what most entrants in this category will build, and Experiment C's numbers either back that claim up or they don't — which is exactly why Section 14's evaluation isn't optional polish, it's the thing the Innovation score actually rests on.

## 18. Build Plan — Phases

Presented as an ordered sequence of phases, not a calendar. Each phase has a clear, checkable exit condition — move to the next phase when the exit condition is genuinely met, not on a fixed schedule.

**Phase 1 — Prove the CV core works at all.**
Local OpenCV 5 install and a "hello world" — load an image, run edge detection and contour analysis, produce annotated output. Exit condition: `cv2.__version__` prints correctly and a single test image produces a sane annotated result.

**Phase 2 — First-pass measurement pipeline.**
Implement part-boundary detection, reference-comparison logic, and the evidence-gap scoring rule, tested against the first handful of self-captured images (a mix of clean and deliberately-defective prints). Exit condition: the system correctly sorts a small hand-labeled batch into confident-pass / confident-fail / uncertain without the agent involved yet.

**Phase 3 — The adaptive loop.**
Wire in `gemini-3.7-flash` for tool selection, implement the 3–4 whitelisted OpenCV tools, and get one full first-pass → agent-call → second-pass → final-decision round-trip working end to end, even ugly, even via a script with no UI.

**Phase 4 — Run the evaluation (Section 14, Experiments A/B/C).**
This is the phase that answers the project's central honest question. Do this before investing in UI polish — the result determines whether the pitch leads with "adaptive agent" or with "measured technical execution."

**Phase 5 — UI and evidence-trace viewer.**
Build the Next.js frontend against the mock mode first, then wire it to the real API once Phase 3/4 are stable. This is also when the mock-mode fallback path for demo-day resilience gets built for real, not left as a "we'll add it later" note.

**Phase 6 — AWS deployment and the COOL benchmark (Experiment D).**
Containerize, deploy to Graviton, run the baseline-vs-COOL comparison, wire up S3/DynamoDB/CloudWatch, set the billing alarm (should already be done by now, per Section 15 — if not, do it now, first).

**Phase 7 — Robustness pass (Experiment E) and documentation.**
Test the 2–3 deliberately ambiguous/adversarial cases, write the architecture diagram and technical report, and write the honest limitations section — this should be written from real test results, not drafted generically and backfilled.

**Phase 8 — Demo rehearsal and submission.**
Record the ≤5-minute video following the structure in Section 22, do a full fresh-deployment test (clone the repo on a clean machine, follow your own setup instructions exactly), and submit.

**A note on scope discipline, carried forward from the retrospective on your last build:** the phases above are ordered so that the *riskiest, most uncertain* work (Phases 1–4) happens before any UI polish, not after. That ordering exists specifically because your own past-project notes flagged scope creep and late-stage discovery of core problems as the two biggest recurring risks — this plan front-loads exactly the parts most likely to reveal a real problem early enough to still fix it.

---

## 19. Repository Structure & File Manifest

```text
loopsight/
├── apps/
│   └── web/                    # Next.js frontend
│       ├── app/
│       │   ├── page.tsx        # upload / camera entry point
│       │   ├── job/[id]/       # evidence-trace viewer
│       │   └── api/            # thin proxy routes to AWS, if needed
│       └── components/
├── services/
│   └── inference/               # Python FastAPI + OpenCV 5
│       ├── main.py
│       ├── cv/
│       │   ├── decode.py
│       │   ├── first_pass.py    # boundary detect, measurements, evidence-gap scoring
│       │   ├── tools.py         # the 3–4 whitelisted reinspection tools
│       │   └── policy.py        # deterministic final-decision logic
│       ├── agent/
│       │   └── tool_selector.py # gemini-3.7-flash call, schema-validated
│       └── tests/
│           └── golden_cases/    # the scripted test clips/images from Section 14
├── infra/
│   ├── docker/
│   ├── aws/                     # IaC or deploy scripts, IAM policy notes
│   └── budget-alarm.md          # the billing alarm setup, documented
├── data/
│   └── self_captured/           # the 30–100 labeled 3D-print images — first-party, freely licensable
├── experiments/
│   └── evaluation_results/      # Experiments A–E outputs, tables, plots
├── reports/
│   ├── technical_report.md      # the required submission report
│   ├── architecture_diagram.png
│   └── limitations.md
├── .env.example
├── README.md
└── LICENSE
```

## 20. Risk Register

| Risk | Mitigation |
|---|---|
| Adaptive loop doesn't actually beat a fixed second-pass heuristic | Section 14's Experiment C vs. B is the direct test; the documented fallback is to keep the product shell and pivot the pitch to technical execution + COOL if the numbers don't support the agentic story |
| First AWS/Graviton/COOL deployment eats far more time than expected — genuinely new territory | Budget Phase 6 as its own real phase, not a footnote at the end; a bare Graviton+Docker+OpenCV round-trip is worth proving early in isolation, before wiring it to the rest of the system |
| Self-captured dataset too small/narrow to mean anything | 30–100 images across several defect types is the realistic, defensible target every source dossier converged on — don't try to exceed it at the cost of the other phases; a small, honestly-labeled set beats an overclaimed large one |
| Demo-day AWS hiccup (cold start, transient failure) | The golden-result fallback path from Section 10 — build it as a real feature, not an afterthought |
| It reads as "just another AI defect detector" to a judge who's seen several this year | The evidence-trace UI and the Section 8 competitive framing exist specifically to pre-empt this — lead every pitch with "decides what to inspect next," never with "detects defects" alone |
| Scope creep — video mode, multi-camera, a full review dashboard all creeping into v1 | Section 18's phase ordering and Section 11's explicit exclusion list exist specifically to catch this before it happens |
| MVTec or another third-party dataset's license creates a submission problem | Section 13's rule: self-captured data ships in the public repo; MVTec, if used at all, stays internal-validation-only and is never redistributed |
| False confidence from an unrepresentative "lucky" demo run | Rehearse with a genuinely ambiguous case (Section 9), not only clean pass/fail examples |
| `gemini-3.7-flash` free-tier limits or terms change between now and submission | Not independently confirmed in this research pass — **[VERIFY]** current limits directly in Google AI Studio before relying on them, and build the golden-result fallback regardless so a live API hiccup never fully breaks a demo |
| A single point of failure in the AWS inference endpoint | Same golden-result fallback; the UI should degrade to a clear "try again" state, never a hard crash |
| **(Revision 2)** Stale buffered webcam frame makes the "second look" inspect the same moment twice, silently | Section 9's frame-freshness engineering — dedicated capture thread, sequence IDs, timestamps shown in the evidence-trace UI. This was the single sharpest, most specific risk raised across three independent adversarial research passes |
| **(Revision 2)** Judge has already seen an OctoPrint/PrintGuard-style AI monitor and mentally files this as the same thing | Lead with the measured Experiment B2 result (Section 14), not the architecture — "beats fixed observation at matched cost" is not a claim any of the existing open-source tools make, because none of them measure it |

---

## 21. Ethical, Legal & Licensing Considerations

**Stakes level:** Moderate, not high. A wrong PASS/FAIL verdict wastes filament and print time — a real but recoverable cost, not a safety-critical failure. This is worth stating explicitly in the report, because it's a genuine point in the project's favor: it avoids the heavier disclaimer/liability burden a safety-monitoring pitch (like the SiteSentinel or SpatialGuard alternatives) would have carried, while still being a real, useful tool.

**Disclaimer, shown in the product, not just the report:** *"LoopSight is a decision-support tool for print-quality inspection. It does not guarantee defect-free output and should not be the sole basis for high-stakes or safety-critical part decisions."*

**Data/privacy — Revision 2 softening.** The earlier draft of this section said self-captured data "avoids licensing questions entirely." That's too absolute, and all three adversarial research passes independently corrected it. The accurate version: **self-capture substantially reduces third-party dataset-licensing exposure — it does not eliminate every consideration.** Kathir owns copyright in his own photographs the moment they're taken, which is the main thing that matters. But a photo can still contain third-party material worth being deliberate about before publishing the dataset: a visible brand logo or proprietary slicer-generated test pattern, or another person in frame. Practical rule: keep the frame to the printed object and the print bed, avoid branded packaging/labels in shot, and get explicit consent if any other person (classmates, makerspace staff) ends up in dataset or demo footage.

**Licensing, restated from Section 13 for completeness:** MVTec-family datasets are CC BY-NC-SA 4.0 (non-commercial, internal validation only, never redistributed). Any pretrained model or library used must be checked individually — Ultralytics YOLO in all current versions is AGPL-3.0-only (confirmed independently across every research pass that checked it), which requires source disclosure for any networked service. If a trained detector gets added past v1, **YOLOX (Apache-2.0)** is the alternative two independent research passes converged on; RF-DETR and D-FINE (both Apache-2.0) are other named options worth a look before committing.

**IP grant, precisely scoped (correcting Section 3's earlier, more cautious framing):** the official rules grant OpenCV/AWS a broad license only over the literal **"Submitted Materials"** — the proposal, technical report, presentation, and video. Private source code, model weights, or datasets that are merely referenced, linked, or demonstrated (not literally included in the submission) stay outside that grant. Practical takeaway: keep the GitHub repo private-by-default if full ownership matters for a possible future Knowledge-Arena-style commercial path, and treat only the required report/video/architecture-diagram package as what's actually being broadly licensed. This doesn't change anything about what's required for judging — a working, judge-accessible endpoint and code are still required deliverables — it just clarifies exactly what rights follow from providing them.

**Bias/fairness:** Lower-stakes than a face- or person-detection system, but not zero — a detector trained or tuned only on light-colored filament, for instance, could underperform on darker filament colors due to contrast differences. Worth a one-line disclosure in the limitations section if the self-captured dataset ends up skewed toward one filament color, which is a realistic risk given a small, quickly-assembled dataset.

**Transparency:** The evidence-trace UI already serves this function organically — a user sees exactly what the system measured and why, which is a stronger transparency story than most competing entries will have, without needing extra design work beyond what Section 9 already specifies.

---

## 22. Demo & Video Script Structure

For the required ≤5-minute judge-accessible video. Structure, not a rehearsed script — fill in the specifics once Phase 4's real evaluation numbers exist.

- **0:00–0:20 — The problem.** A print in progress, an ambiguous irregularity, the honest question: is this fine or should I stop it?
- **0:20–0:55 — First inspection.** Run a clean sample through the system live — show the first-pass measurement and a confident PASS, fast.
- **0:55–1:25 — The wow moment.** Run a genuinely ambiguous sample — show the `UNCERTAIN` state, the agent's tool selection, the second pass, and the evidence trace changing the outcome, on screen, not described in voiceover.
- **1:25–1:55 — The final decision and why it's trustworthy.** Show the `REVIEW`/`PASS`/`FAIL` verdict alongside the full Perception → Decision → Tool Call → New Evidence → Decision trace.
- **1:55–2:40 — Technical depth.** Architecture diagram, AWS deployment, the Experiment A/B/C numbers on screen — this is where the Innovation and Technical Execution claims get their actual evidence, not just an assertion.
- **2:40–3:30 — COOL benchmark.** The baseline-vs-COOL comparison from Experiment D, shown as real numbers, not a claim.
- **3:30–4:15 — Honest limitations.** At least one real failure case from Experiment E, handled gracefully — this is required submission evidence, and it's also a credibility signal to judges who've seen too many demos that only show the happy path.
- **4:15–4:50 — Responsible design.** The disclaimer, the licensing discipline around MVTec, the human-approval gate.
- **4:50–5:00 — Close.** The one-sentence thesis from Section 4, restated plainly.

## 23. AWS Compute Grant Proposal — Draft Outline

The competition's $150 compute grant (Section 2) requires a short proposal covering six specific points. Worth submitting early in the build regardless of the odds of being one of the 50 selected teams — drafting it forces the architecture decisions in this document into a tight, judge-facing form early, which pays off later in the technical report anyway.

1. **Planned OpenCV 5 image/video analysis:** Classical CV pipeline — part-boundary detection, reference-image structural comparison, edge-continuity and geometric-deviation measurement — applied to desktop 3D-print quality inspection, with an adaptive second-pass reinspection step for ambiguous cases.
2. **Planned AWS architecture and services:** API Gateway + Lambda (orchestration) → Graviton (ARM64) container running OpenCV 5 + COOL (inference) → S3 (evidence storage) + DynamoDB (job metadata) → CloudWatch (observability and the COOL-vs-baseline benchmark).
3. **High-level architecture diagram or technical description:** Section 10's diagram, or a simplified one-paragraph version of it.
4. **Target users/beneficiaries:** Desktop 3D-printing hobbyists and small print-farm operators — Section 7's personas, condensed.
5. **Proposed evaluation method and judge demonstration:** Section 14's Experiments A–E, and Section 22's live-demo structure.
6. **COOL / Agentic Vision path intent:** Both — Section 16 explains why the product design targets each award as a genuine consequence of the architecture rather than a bolt-on.

Plus a short team bio, honestly stated: solo second-year B.Tech AI & Data Science student, prior hackathon experience (name the Prometheus/SPEED AI Challenge submission if it strengthens the bio), comfortable with the Next.js/Vercel/cloud-API side of the stack, treating the AWS/Graviton/OpenCV side as genuinely new territory being learned specifically for this build.

---

## 24. Glossary

- **Adaptive/active reinspection:** Deciding what additional visual evidence to gather based on where the first inspection pass was ambiguous, rather than always running a fixed second check or none at all.
- **Agentic Vision:** The competition's special award category for projects where OpenCV's own visual output changes a later decision, tool call, or action — not just a static detect-and-display pipeline.
- **COOL:** Cloud-Optimized OpenCV Library — an OpenCV variant tuned for AWS Graviton (ARM64) workloads.
- **Evidence-gap:** The structured field naming what specifically is ambiguous about a first-pass inspection result, used to drive the agent's tool selection.
- **Graviton:** AWS's ARM64-based EC2 processor family; the required substrate for COOL.
- **Reason code:** A small, fixed categorical field the agent returns to explain its tool choice, deliberately not free text, so the product logic never has to parse or trust open-ended model reasoning.

---

## 25. Source Register — What's Verified vs. What Needs Rechecking

**High confidence, live-checked 30 Aug 2026:** competition deadline, team-size cap, prize structure, compute-grant amount and requirements, the official judging rubric, the mandatory OpenCV5+AWS requirement, `gemini-3.7-flash`'s current status as the actively-recommended coding/agent model, `gemini-2.0-flash`'s shutdown, MVTec AD's CC BY-NC-SA 4.0 license.

**Medium confidence, inherited from the source research and not independently re-verified in this pass:** exact current AWS Graviton free-tier instance eligibility, the exact current Ultralytics-YOLO AGPL-3.0 status across all model versions, the precise current OpenCV 5 Python wheel version number.

**Must be rechecked immediately before implementation, not assumed from this document:** exact `gemini-3.7-flash` free-tier RPM/RPD limits in Google AI Studio, current COOL version and its officially-validated Graviton instance type, whether the live Official Rules page has been amended since 30 Aug 2026, and Kathir's own AWS account creation date (determines Free Plan credit expiry).

---

## 26. Reference Implementation Sketches

Not production code — these are concrete starting skeletons so Phase 1–3 of the build plan don't start from a blank file. Every function signature here matches the data contracts in Section 12 exactly.

**`services/inference/cv/first_pass.py` — the deterministic first-pass measurement stage:**

```python
import cv2
import numpy as np
from dataclasses import dataclass, field

@dataclass
class RegionEvidence:
    x: int
    y: int
    w: int
    h: int
    edge_continuity: float
    reference_similarity: float
    layer_alignment_deviation: float

@dataclass
class FirstPassResult:
    status: str  # "CONFIDENT_PASS" | "CONFIDENT_FAIL" | "UNCERTAIN"
    regions: list[RegionEvidence]
    evidence_gap: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)

# Thresholds are placeholders — tune these against the self-captured
# labeled set in Phase 2, do not ship un-tuned defaults.
EDGE_CONTINUITY_CONFIDENT_FAIL = 0.35
EDGE_CONTINUITY_CONFIDENT_PASS = 0.85
CONTRAST_MIN_FOR_CONFIDENCE = 0.4

def measure_region(frame: np.ndarray, reference: np.ndarray, roi: tuple[int, int, int, int]) -> RegionEvidence:
    x, y, w, h = roi
    crop = frame[y:y + h, x:x + w]
    ref_crop = reference[y:y + h, x:x + w]

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    edge_continuity = float(np.count_nonzero(edges)) / edges.size

    ref_gray = cv2.cvtColor(ref_crop, cv2.COLOR_BGR2GRAY)
    # Structural similarity against the known-good reference — classical,
    # deterministic, no trained model required for v1.
    diff = cv2.absdiff(gray, ref_gray)
    reference_similarity = 1.0 - (float(np.mean(diff)) / 255.0)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    layer_alignment_deviation = _contour_deviation_score(contours)

    return RegionEvidence(x, y, w, h, edge_continuity, reference_similarity, layer_alignment_deviation)

def score_evidence(regions: list[RegionEvidence], local_contrast: float) -> FirstPassResult:
    worst = min(regions, key=lambda r: r.edge_continuity)

    if local_contrast < CONTRAST_MIN_FOR_CONFIDENCE:
        return FirstPassResult(
            status="UNCERTAIN",
            regions=regions,
            evidence_gap=["low local contrast — cannot confirm edge deviation"],
            allowed_tools=["reinspect_roi", "compare_to_reference", "measure_edge_continuity", "track_across_frames"],
        )

    if worst.edge_continuity <= EDGE_CONTINUITY_CONFIDENT_FAIL:
        return FirstPassResult(status="CONFIDENT_FAIL", regions=regions)
    if worst.edge_continuity >= EDGE_CONTINUITY_CONFIDENT_PASS:
        return FirstPassResult(status="CONFIDENT_PASS", regions=regions)

    return FirstPassResult(
        status="UNCERTAIN",
        regions=regions,
        evidence_gap=["edge continuity in ambiguous middle band"],
        allowed_tools=["reinspect_roi", "compare_to_reference", "measure_edge_continuity"],
    )
```

**`services/inference/agent/tool_selector.py` — the bounded agent call:**

```python
from google import genai
from pydantic import BaseModel
from typing import Literal

# Whitelist enforced twice: once in the schema, once again explicitly
# before any tool actually executes. Never trust the schema alone.
ALLOWED_TOOLS = {"reinspect_roi", "compare_to_reference", "measure_edge_continuity", "track_across_frames"}

class ToolCall(BaseModel):
    tool: Literal["reinspect_roi", "compare_to_reference", "measure_edge_continuity", "track_across_frames"]
    arguments: dict
    reason_code: str  # controlled vocabulary — validate against a fixed enum, not free text

def select_next_tool(first_pass_result, client: genai.Client) -> ToolCall:
    # NOTE: the raw image is deliberately NOT sent here — only the
    # structured evidence-gap output. The model's job is choosing a
    # tool, not re-judging the image itself.
    response = client.models.generate_content(
        model="gemini-3.7-flash",
        contents=[{
            "text": (
                "Given this inspection evidence gap, choose exactly one tool "
                f"from {sorted(ALLOWED_TOOLS)} to resolve the ambiguity. "
                f"Evidence gap: {first_pass_result.evidence_gap}. "
                f"Regions: {first_pass_result.regions}."
            )
        }],
        config={"response_mime_type": "application/json"},
    )
    call = ToolCall.model_validate_json(response.text)
    assert call.tool in ALLOWED_TOOLS, f"Model returned a tool outside the whitelist: {call.tool}"
    return call
```

**`apps/web/app/job/[id]/page.tsx` — evidence-trace viewer, structural sketch:**

```tsx
type JobResult = {
  status: "PASS" | "REVIEW" | "FAIL";
  firstPass: { evidenceGap: string[]; regions: RegionEvidence[] };
  agentCall?: { tool: string; reasonCode: string };
  secondPass?: { regions: RegionEvidence[] };
  finalDecision: { decision: string; confidenceBand: string; humanApprovalRequired: boolean };
};

export default async function JobPage({ params }: { params: { id: string } }) {
  const job = await fetchJob(params.id); // typed against the GET /jobs/{job_id} contract in Section 12

  return (
    <main className="mx-auto max-w-3xl p-6">
      <EvidenceTraceStep label="Perception" data={job.firstPass} />
      {job.agentCall && (
        <EvidenceTraceStep label="Agent Decision" data={job.agentCall} />
      )}
      {job.secondPass && (
        <EvidenceTraceStep label="New Evidence" data={job.secondPass} />
      )}
      <FinalDecisionCard decision={job.finalDecision} />
    </main>
  );
}
```

## 27. Testing Strategy

**Golden-case test set (build this before touching the UI):** the same 30–100 self-captured images from Section 13, split into a labeled reference set — `data/self_captured/golden_cases/` — with each image's true label (`clean`, `layer_shift`, `stringing`, `warping`, `under_extrusion`, `blob`, `elephants_foot`) recorded in a single `labels.csv`. This set is used three times: once for Phase 2's manual sanity check, once for Section 14's Experiments A–C, and once as an automated regression check so a later code change can't silently break something that used to work.

**Unit-level tests (`services/inference/tests/`):** each classical CV function in `first_pass.py` and `tools.py` gets a direct test against a small, hand-picked input where the correct output is obvious — e.g., a synthetic image with a clean straight edge should score high on `edge_continuity`; a synthetic image with a deliberately broken edge should score low. These don't need real photographs; synthetic test fixtures are faster to write and easier to reason about for pure geometry functions.

**Integration test — the full loop:** one scripted test that runs a genuinely ambiguous golden-case image through the entire pipeline (first pass → agent call → second pass → final decision) and asserts that the agent loop actually fires and changes the outcome. This is the single most important test in the whole suite — it's the automated version of the "smallest test case that would prove the mechanic works" question from the original research prompt, and it should be run before every demo rehearsal, not just once during development.

**Agent-call testing without burning API quota:** record a handful of real `gemini-3.7-flash` responses during development and replay them as fixtures for routine test runs, calling the live API only when specifically testing the agent-integration path itself. This keeps the test suite fast and avoids rate-limit surprises during iteration.

**What NOT to test, deliberately, given solo/time-boxed constraints:** full end-to-end browser automation (Playwright or similar) is a reasonable thing to skip for a hackathon-scale build — manual click-through testing of the UI is a fine tradeoff here, unlike the CV correctness tests above, which are cheap to write and catch real regressions that manual testing would miss.

---

## 28. IAM & Security Notes

**Principle:** the judge-accessible demo endpoint has no user authentication, so everything else has to be scoped tightly instead.

- **IAM role for the Graviton inference container:** least-privilege — write access only to the specific S3 prefix used for evidence images, write access only to the specific DynamoDB table used for job metadata, no broader account permissions. Write this policy out explicitly in `infra/aws/iam-policy.md` as part of the submission's "responsible cloud delivery" evidence, not just configured silently in the console.
- **S3 access for evidence images:** short-lived signed URLs generated per job, not a public bucket. This is both a real security practice and a direct, checkable answer if a judge asks how personal/sensitive images are handled — even though this project's images are of 3D-printed objects, not people, the same discipline is worth demonstrating.
- **API Gateway:** a single demo token in the request header, checked at the Lambda/FastAPI layer, is sufficient for a hackathon-scale public demo — don't build a real user-auth system that adds complexity without adding anything judges score on.
- **Secrets management:** the `gemini-3.7-flash` API key and any AWS credentials live in environment variables (Lambda environment config, Vercel environment variables) — never committed to the repository, and the `.env.example` file in the repo shows the required variable names with placeholder values only.
- **Rate-limit defense on the agent call:** cap `max_agent_steps` per job (Section 12's input contract already includes this field) so a malformed or adversarial input can't trigger an unbounded chain of tool calls.

---

## 29. Lessons Carried Forward From Your Last Build

Worth stating explicitly, since this document exists specifically to make the next attempt faster and calmer than the last one, not just technically different.

- **Scope discipline held real weight last time, and holds here too** — Section 11's explicit exclusion list and Section 18's phase ordering exist for exactly the reason your own retrospective named: the temptation to add "just one more feature" is the single most common way a solo hackathon build runs out of runway before the core loop is solid.
- **Verify raw evidence, not agent summaries** — this document itself follows that rule: every fact in Section 2 is tagged with where it came from and when it was checked, and every place the source research disagreed with a live-checked fact, the live fact won, not the more confidently-worded document.
- **Deploy early, not at the end** — Section 18 deliberately puts the first AWS/Graviton round-trip in Phase 6, but flags it in Phase 1 planning as genuinely new territory worth de-risking early with a bare-bones deployment test, rather than discovering deployment problems in the last week the way infrastructure surprises tend to happen.
- **One deliberate design pass, not endless iteration** — the architecture in Section 10 and the mechanic in Section 9 are meant to be locked once Phase 4's evaluation results come back, not continuously re-argued with yourself for the rest of the build. If Experiment C beats Experiment B, the design is settled; if it doesn't, Section 20's fallback is settled too. Either way, that's the one deliberate pivot point, not an open-ended one.
- **Gather independent opinions when a decision is in real doubt** — exactly how this document itself got built: six independent research passes, cross-checked against live sources, with disagreements resolved rather than averaged. The same pattern is worth repeating for any genuinely uncertain decision that comes up mid-build (a defect-detection threshold, a UI choice a test user reacts badly to) rather than defaulting to whichever option happened to get implemented first.


---

*End of specification. This document is a starting map, not a contract — treat every **[VERIFY AT BUILD TIME]** marker as a real task, not a formality, and update this document as those checks resolve.*
