# LoopSight — evidence-guided visual screening

LoopSight uses **OpenCV 5**, a bounded action controller and a deterministic
screening policy to inspect images and request better evidence when uncertain.
It targets the **OpenCV AI Competition 2026 powered by AWS**.

The primary workflow measures checkerboard visibility behind a water sample.
Glare, exposure, framing and image detail can cause abstention. A follow-up
photo under changed lighting is checked against the retained original before
it influences the result. Crack-like pixel features and FDM surface inspection
remain experimental profiles.

**These are relative image measurements.** NTU, drinking-water safety,
structural safety and physical crack widths have not been validated and are
not reported as measurements. Confidence labels are heuristic, not calibrated
probabilities. [Current progress and remaining gaps](reports/BUILD_PROGRESS.md)
contains the latest evidence; [the original audit](reports/STRICT_TECHNICAL_REVIEW.md)
records why historical claims were withdrawn.

## Implemented

- Real uploaded-image OpenCV execution, eight bounded diagnostic tools and
  optional Gemini tool selection. Final verdicts come from explicit policy.
- First-pass evidence retained across workers, using bounded SQLite locally
  or shared private S3 objects in cloud mode, with expiry and exact image hashes. Follow-ups reject duplicates,
  incompatible framing and inconsistent appearance. Visual checks do not prove
  physical sample identity or acquisition authenticity.
- Actual first/second images accessible during evidence retention, with private
  no-store responses. Expiry, missing evidence and backend failures remain errors.
- Separate provenance for uploaded-image computation, synthetic benchmarks and
  explicitly enabled demo fixtures. Unknown job IDs return 404.
- JSON/PDF results and downloadable evidence ZIPs with image-unit scope, policy
  snapshots, file manifests and observation counts. Same-image
  enhancement is not counted as a new capture or used to clear uncertain water.
- Manifest-based paired evaluation with exact requested-input budgets,
  preparation-group/image split leakage checks, coverage and false-clear metrics.
- A measured-results explorer at `/evaluation`, live backend/storage-read
  status, and `/capture-guide` with a printable checkerboard.

## Run locally

Use Python 3.13 and Node 20 or newer. From the repository root:

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt pytest httpx
GEMINI_API_KEY= DYNAMO_TABLE_NAME= .venv/bin/python -m uvicorn services.inference.main:app --port 8000
```

In a separate terminal:

```bash
cd apps/web
npm ci
INFERENCE_API_URL=http://127.0.0.1:8000 npm run dev
```

Open http://localhost:3000. Backend `/health`, `/ready`, `/version`, `/samples` and
`/mcp/tools` expose readiness, runtime metadata, synthetic scenarios and tool
schemas. Fonts are bundled locally. `.env.example` documents optional settings.
Do not build and run a frontend server concurrently against the same `.next`.

On Vercel, real inference requires `INFERENCE_API_URL`. Missing configuration
returns 503. Only server-side `DEMO_MODE=golden` enables explicitly labeled
fixtures; a request cannot enable demo mode. For AWS operation, use the
[deployment guide](infra/aws/README.md) and set `LOOPSIGHT_EVIDENCE_BUCKET`.
This selects shared S3 for jobs/captures; Lambda `/tmp` does not share SQLite.
When backend token protection is enabled, set the matching server-only
`INFERENCE_API_TOKEN` on Vercel. Prepared infrastructure is not a verified AWS
deployment. No physical field performance is claimed by this checkout.

## Verify and evaluate

```bash
GEMINI_API_KEY=disabled .venv/bin/python -m pytest services/inference/tests -q
.venv/bin/python services/inference/scripts/evaluate_captures.py data/synthetic_capture_manifest.json --json /tmp/paired-capture-regression.json
cd apps/web
npm test
npm run build
# Real desktop/mobile workflows; installs Chromium once if needed:
npx playwright install chromium
npm run test:e2e
```

The committed dataset is entirely synthetic despite its historical
`data/self_captured` directory name. The current binary-labeled regression
manifest has 34 primary fixtures, five generator-family groups and six supplied
synthetic companion images; six ambiguous-label fixtures are excluded.
Single-pass accuracy including abstentions is **47.1%**; fixed, matched and
adaptive acquisition each achieve **64.7%**, requesting the same six extra
images. **This is a tie, not evidence of an adaptive advantage or field accuracy.**
The detailed [report](reports/evidence/2026-10-18-paired-capture-regression.json)
records hashes, thresholds and runtime versions. The old `run_experiments.py`
is retained as a legacy diagnostic, not a validated matched-budget comparison.

To verify persistence with the production frontend and backend running:

```bash
.venv/bin/python services/inference/scripts/smoke_recapture.py prepare
# Restart only your backend, preserving the same SQLite file.
.venv/bin/python services/inference/scripts/smoke_recapture.py verify
```

This synthetic transport check requires different backend runtime IDs and
verifies retained first-pass evidence, pixel-identical capture retrieval and
duplicate rejection. It does not validate physical measurements.

Collect genuine independent data using the
[capture protocol](data/captures/README.md). The [current rules recheck](reports/COMPETITION_RULES_RECHECK.md) confirms that
teams without a grant proposal remain eligible for all prizes, and lists final
submission requirements. No proposal or final entry was submitted by this agent.

Cloud configuration is in `infra/aws/template.yaml`; it passes cfn-lint and the
pinned runtime resolves to ARM64 wheels. These checks do not establish actual
AWS execution. Upload requests are capped at 4 MB, photos at 3.5 MB in the UI,
and analysis images are resized to at most 1024 pixels per side. See the current
technical report for retention, bearer-link access and download-size limits.
