# LoopSight: strict technical review and ten-day build plan

> Historical foundation-stage audit. See [BUILD_PROGRESS.md](BUILD_PROGRESS.md)
> for subsequent image-unit, persistent-recapture and exact-budget evaluation
> implementation, updated verified official sources, assessment and open gaps.

Review date: 18 October 2026. Target confirmed by the owner: OpenCV AI Competition 2026 powered by AWS, https://opencv26.devpost.com/. Presentation/video quality is excluded from this assessment.

## Assessment

My provisional engineering assessment is **about 53/100 after this foundation patch**, compared with about 48/100 for the audited baseline. This is a judgment about demonstrated readiness, not a prediction of an actual judge's score, ranking, or probability of winning. The previous repository claim of 97/100 is not an independent evaluation.

The following weights come from the repository's competition specification. Attempts to verify the current official Devpost rules and OpenCV page returned proxy CONNECT 403, so they remain unverified against the current official text. If confirmed rules differ, rescore before choosing award-specific work. Excluding the specification's 10 presentation/documentation points leaves 90 points; normalize the technical subtotal to 100.

| Criterion | Baseline | After foundation changes | Strict assessment |
|---|---:|---:|---|
| Technical execution | 18/30 | 21/30 | Real OpenCV processing and useful tests; packaging and error handling improved. Physical measurement validity and field robustness remain unproven. |
| Innovation | 10/20 | 10/20 | A sensible application of established active perception. A measured advantage over strong conventional controls has not been demonstrated. |
| Real-world impact | 6/20 | 6/20 | Plausible use case; no independently validated field results, calibrated reference measurements, or user outcome study was found. |
| Functional user experience | 6/10 | 7/10 | Upload/capture workflow exists; truthful errors and provenance improved. Physical mobile/camera acceptance remains untested here. Visual polish is not scored. |
| Cloud delivery/reproducibility/responsible operation | 3/10 | 4/10 | Local production build and source packaging check pass. Actual AWS execution, durable cross-instance jobs and the public deployment are unverified. |
| **Technical subtotal** | **43/90** | **48/90** | **Approximately 48/100 before; 53/100 after normalization.** |

An unfulfilled mandatory AWS requirement could affect eligibility rather than merely deduct points. A 95+ target requires stronger evidence in every weak category; adding features alone does not supply it. No competition-relative winning probability can be estimated without comparable entrant/judge data.

## What is verified

- Code baseline: `3fc2e38758373ddbb5f90b93af9c065d00aabc75`; its code is unchanged from `e0b7a8e` and its extra commit adds the handover report.
- Original backend suite: 52 passed, one optional live-Gemini test skipped.
- Synthetic provenance: regenerating the dataset into a temporary directory produced **46/46 byte-identical committed PNG files**, representing 40 primary samples and six companion images. No original dataset file was overwritten.
- Water evaluation reproduced: A=55%, B=40%, B2=45%, C=100%; C second-look trigger rate=60%, B2=40%.
- Crack evaluation reproduced on six generated fixtures: A=66.67%, B=100%, B2=66.67%, C=100%; C triggers=33.33%, B2=0%.
- Local real OpenCV execution through the frontend proxy returns FAIL for the turbid fixture and PASS for the shadow-confounded crack fixture. This verifies the running pipeline, not real-world accuracy.
- The revised frontend production build succeeds, with bundled Inter fonts and no Google Fonts download.
- Foundation validation: 72 backend tests passed, one live-Gemini test skipped; nine frontend API tests passed. Production-server smoke requests verified corrupt upload=400, unknown job=404, stored synthetic provenance, correct fixture decisions and the home page.
- The Lambda source packaging regression test copies exactly the Dockerfile's COPY inputs to an isolated temporary directory, imports the application and runs an inspection without the checkout or test package. It is **not** an ARM64 container or AWS deployment test. The available Docker builder advertises amd64 only.

## Findings that would concern a strict technical jury

| Priority | Finding and evidence | Required resolution |
|---|---|---|
| P0 | `data/self_captured` is entirely generated from `sample_frames`/the former `tests.synthetic`. Labels such as physical dataset and self-captured are unsupported for these files. | Preserve the fixtures, label them synthetic, and collect an independently documented physical dataset. |
| P0 | The handover calls NTU values certified and describes direct consumption/potability verification. `estimate_physical_ntu` is an uncalibrated formula over an image heuristic. | Remove certification/potability claims. Without instrument-based calibration, expose a relative clarity proxy, not a certified NTU measurement. |
| P0 | Crack mm values use a default 0.10 mm/px; uploads supply no measured scale reference. | Require a physical scale/marker calibration, account for resizing and perspective, report error bounds; otherwise report pixels and unknown physical scale. |
| P0 | A missing/unreachable inference backend could return hash-selected golden verdicts. Unknown job IDs could resolve to an invented successful result. | Fixed in this patch: errors stay errors; fixtures require explicit demo mode; unknown demo IDs return 404. Verify production settings/deployment too. |
| P0 | Lambda startup used out-of-range parent indexing at `/var/task/main.py`, omitted `demo_golden.py`, and benchmark generation imported unshipped tests. | Fixed at source: safe path lookup, included runtime modules, shared synthetic sample module and isolated packaging regression. Actual ARM64 deployment still required. |
| P1 | B2 does not match C's budget. The current output says 40% vs 60% on water and 0% vs 33.33% on cracks. | Allocate an exact number of eligible second captures with a deterministic full-sample hash, report realized budget, and test equality. Count physical observations separately from processing calls. |
| P1 | Experiment C manufactures a brighter second image from the first. The loader skips real companion images and returns only `(label, frame)`. | Load paired captures and capture metadata. Never describe normalization/reprocessing as a newly acquired physical observation. |
| P1 | The crack fixed two-pass control already ties C at 100%. The tested controller is deterministic; this is not evidence of Gemini's benefit. | Compare single-pass, strong fixed processing, fixed two-capture, deterministic adaptive and optional Gemini-adaptive controls on the same held-out cases and budgets. Report ties and losses. |
| P1 | Synthetic generators, thresholds, labels and test cases are tightly related; no independent holdout or grouped split was found. | Freeze policy/calibration before blind testing. Split by physical preparation/session/device; keep paired images in one split. |
| P1 | Inpainting/contrast enhancement can increase the very contrast/sharpness metrics used to declare a clear result. Residual glare is assigned `glare_frac * 0.15`. | Re-measure actual valid pixels and mask coverage; do not treat synthesized pixels or metric boosting as recovered sensor evidence. Request a new capture when evidence is occluded. |
| P1 | `track_across_frames` measures shift but returns the last frame's evidence; it does not establish same-sample identity or apply registration/fusion. | Validate distinct captures, overlap, scene consistency and registration confidence. Reject unrelated/poorly aligned frames and document the actual aggregation rule. |
| P1 | Request-to-request first-frame state is kept in `FRAME_CACHE`, which is process-local. | Persist an inspection session and frame references with expiry; test cold starts and requests landing on different workers. |
| P1 | DynamoDB calls log and swallow failures. The deploy script grants logging permissions but no table read/write permissions. Inline overlay JSON may also exceed DynamoDB's item-size limit. | Add scoped table permissions, surface persistence failures, store large evidence as objects, and prove retrieval from a fresh instance. |
| P1 | The handover claims measured Graviton3/c7g latency, but the frontend contains the same static timing numbers in demo fixtures. | Preserve real trace/runtime identifiers and cold/warm measurements. Remove hardware attribution until measured on that hardware. This patch removes the UI's unconditional AWS hardware label and invented timing defaults. |
| P1 | MCP was a small custom JSON-RPC endpoint, not a demonstrated SDK/client transport integration. Some malformed params returned 500; initialization notifications received error responses. | This patch improves validation, notification handling, declared inputs and tool bounds. Still verify a supported MCP transport with an actual SDK client before claiming full interoperability. |
| P1 | Tool selection previously accepted billion-scale resize arguments and 1,000-step chains. Gemini timeout seconds were passed into a milliseconds field; retries/model guesses expanded the request budget. | Fixed validation: finite bounded parameters, at most four distinct tools, per-inspection permitted tools, SDK milliseconds, one request attempt, explicit selector provenance. No live API result is claimed. |
| P2 | No calibrated confidence model, false-clear rate or useful failure breakdown is reported. `REVIEW` accuracy mixes abstention with a physical ground-truth class. | Separate truth from abstention; report false-clear/false-alarm rates, coverage, selective risk, confusion matrices and uncertainty intervals. |
| P2 | Public input endpoints have limited resource protection; decoded pixel checks occur after decoding. CPU-heavy CV runs directly inside async request handlers. | Bound body/decode work, use a bounded execution pool/concurrency policy, rate limits and explicit resource/time budgets. Load-test realistic image sizes. |
| P2 | Python requirements use lower bounds rather than locked versions; Lambda uses Python 3.12, CI 3.13. | Lock compatible dependencies and test the actual supported deployment runtime/architecture. The web lockfile is retained. |
| P2 | A web manifest is described as offline field capability, but no service worker or offline inference path was found. | Remove the claim or implement/test a clearly scoped offline capture queue; do not imply offline inference exists. |
| P2 | The retained handover, submission narrative and checklist contain unsupported and mutually inconsistent deployment, physics and award claims. | Treat the new review as the current status record; reconcile all submission documents with measured evidence before submission. |

## Work completed in the foundation branch

1. Repaired Lambda path lookup and runtime file packaging; production samples no longer import the test package.
2. Removed automatic fixture fallback from inspection/job proxies, preserved backend error statuses, and made unknown demo jobs return 404.
3. Restricted fixture responses to explicit `DEMO_MODE=golden`; caller form fields cannot enable demo mode in the web proxy.
4. Added stored execution provenance for uploaded-image OpenCV, synthetic benchmark execution and demo fixtures; exposed it on result pages and PDF exports.
5. Labeled the benchmark library synthetic and physical unit estimates unvalidated. Removed unconditional AWS hardware claims and invented timing substitutes from the telemetry panel.
6. Bounded tool parameters and chains, checked per-inspection tools, corrected Gemini timeout units, honored `GEMINI_MODEL`, and limited SDK retries.
7. Kept missing-second-capture inspections in REVIEW rather than silently substituting an upsampled image. MCP tracking no longer duplicates the same frame into two captures.
8. Improved RPC input validation and initialization notification behavior; added discoverable image inputs and parameter limits.
9. Bundled licensed Inter font files through a locked package, allowing the production build without Google Fonts egress.
10. Added backend/packaging and web API regression tests and ran the new API checks in CI.

These changes fix engineering defects. They do not validate NTU/mm accuracy, demonstrate field impact, deploy AWS resources, or establish 95-point performance.

## Remaining build, in order

### Days 1–2: trustworthy core and deployed evidence

- Finish a single primary use case: **relative water-clarity screening under controlled captures**. Keep crack/FDM profiles explicitly experimental until separately validated.
- Replace physical NTU/tier output with a dimensionless relative clarity score unless calibration evidence exists. Gate physical crack units on a known scale.
- Use a reference region/clear-water baseline, a controlled target location and geometry checks. Retain raw pixels, mask coverage and capture conditions.
- Make acquisition a durable state machine: first capture → reason for uncertainty → specific lighting/position instruction → new capture → consistency check → decision or abstention.
- Verify deployed inference version, runtime architecture, storage round trip, real upload and error behavior. Add a version/health check to CI against the deployment when access is supplied.

### Days 2–5: independent data and defensible evaluation

- Aim for 30–50 independent sample preparations and 150–300 primary images across at least three phones, multiple lighting conditions and multiple capture sessions. This is a collection target, not existing evidence or a guarantee of adequate statistical power.
- Keep preparation/session/device IDs, timestamps, lighting labels, known sample preparation, image hashes, rights/consent and reference readings where available. Generate manifests automatically; preserve actual originals.
- Choose a grouped calibration/validation/blind-test split before tuning. Do not use near-identical frames or a companion from the same preparation across splits.
- Rebuild the evaluator with actual paired frames, exact observation budgets and all strong controls. Export per-case results and reproducible run metadata.
- Report false-clear rate as a central outcome, plus coverage, error types, group-aware confidence intervals, p50/p95 latency and cost per inspection.
- If an instrument/reference standard is accessible, fit and independently validate the optical mapping under documented geometry. Otherwise keep NTU disabled and explain the scope precisely.

### Days 5–7: differentiate with measured acquisition value

- Add evidence-driven recapture instructions for glare, exposure, skew and settled material; show before/after evidence from actual capture pairs.
- Compare expected benefit per extra observation and per second of latency. Include cases where another observation did not help and where the system declined to decide.
- Build a reproducible evidence bundle: raw capture hashes, capture/calibration metadata, selected action, actual selector mode, tool arguments, outputs, thresholds, software version, result and timings.
- Provide a benchmark explorer over the frozen held-out results with per-case successes and failures. Do not populate it from golden fixtures.
- Exercise a real MCP client if the agentic track values interoperability. Keep the deterministic controller as an explicit comparison; only claim LLM value if measured.

### Days 7–9: operational and user validation

- Configure durable evidence/session storage with expiry, scoped permissions, deletion and clear handling of storage outages. Test more than one worker and a backend restart.
- Test camera permission denial, mobile upload, absent target, invalid files, interrupted requests, duplicate/unrelated second frames, unknown IDs and unsupported profiles end to end.
- Test load and cold starts; enforce measured concurrency/time budgets. Confirm all UI/PDF/JSON surfaces retain source/calibration labels.
- Run 5–10 structured target-user tasks to measure completion, capture retries, time to usable evidence and understanding of limitations. Report observations instead of an assumed impact multiplier.

### Day 10: freeze and verify

- Freeze dependencies, thresholds and the final blind test; rerun from a clean environment and the deployed stack.
- Resolve all P0/P1 findings or explicitly remove the affected capability/claim.
- Reconcile README, report, checklist and handover statements with the evidence bundle and the current official rules.
- Verify substantive OpenCV 5 execution and the meaningful AWS component required by the confirmed rules. Claim COOL only if that separate integration and its measured value actually exist.
- Preserve rollback/deployment identifiers. Presentation production is outside this score and plan at the owner's request.

## Strong additions versus low-return expansion

Highest-value new capabilities are a **capture calibration workflow**, **durable recapture sessions**, **paired-image validation**, **fair blind evaluation runner**, **evidence export/replay**, and **deployment smoke checks**. Each directly addresses a demonstrated weakness.

Do not spend the critical path on another inspection domain, generic chat, more animated dashboards, unsupported hardware claims, or a multi-agent controller whose benefit has not been measured. A focused, falsifiable result is more defensible than a larger list of unvalidated capabilities.

## Access and outside prerequisites

- GitHub HTTPS read/fetch works. API requests to `api.github.com` are denied by the current proxy, so account permissions/CI/PR state are not verified here. Branch push is checked separately and reported only if successful.
- Official Devpost/OpenCV pages and `loopsight.vercel.app` are also denied by the running network policy. Required domains are saved in the environment draft; the user must save the network settings before those requests can be retried.
- No Vercel-specific credential or project binding was found. A Vercel Git integration may exist, but cannot be assumed from the repository. Use secure environment settings or the platform's connection flow for the project-scoped access needed to inspect/deploy it; never paste tokens into chat.
- AWS config/credential files were absent in this machine; boto3 credential resolution failed with `ProfileNotFound`. No AWS CLI deployment or AWS resource changes were performed. A valid account/project-scoped authentication path and the existing backend deployment identifier are needed.
- Live Gemini was not exercised. It is optional for the deterministic local workflow; securely configure a supported model/key only when testing that comparison.
- Physical sample capture, reference readings and genuine user study evidence cannot be manufactured in code. Those require the owner's real-world participation.

## Sources and their limits

Primary implementation evidence: `services/inference/main.py`, `cv/first_pass.py`, `cv/tools.py`, `cv/policy.py`, `agent/tool_selector.py`, `storage.py`, `Dockerfile.lambda`, `scripts/run_experiments.py`, `scripts/generate_benchmark_dataset.py`, `apps/web/src/lib/mock-data.ts`, API routes and the executed checks above.

The owner's handover `LOOPSIGHT_FULL_SYSTEM_AND_SESSION_REPORT.md` and the repository's specification were reviewed as project records. Their assertions about certified calibration, AWS measurements, competition facts, deployed status and a 95+/97 rating are not independent proof. No private projects or information from other ChatGPT users were used.
