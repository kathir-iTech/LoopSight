# LoopSight — current technical report

Updated 18 October 2026. Prepared implementation and local evidence are reported
separately from unverified cloud deployment and physical validation. This replaces
the prior technical draft; historical claims remain only in Git history.

## Problem, users and scope

LoopSight investigates uncertainty-aware relative water-clarity image screening.
A checkerboard viewed through a sample supplies an image reference. Glare,
lighting, framing and settled material can confound a single view. The intended
interaction is measurement → uncertainty → specific new evidence → deterministic
screening or abstention. User benefit and field reliability remain hypotheses
until measured with independent samples and target users.

PASS indicates the policy found high pattern visibility; FAIL indicates a low
visibility/image-feature signal; REVIEW means insufficient evidence. Missing
reference targets are rejected with NO_PATTERN_DETECTED. These outcomes do not
certify water safety, turbidity in NTU, physical crack width or structural safety.
Image confidence labels are heuristic, not calibrated probabilities.

## Implementation

The Next.js 15.5.23/React interface accepts camera/upload input, shows original and
follow-up evidence, exposes failure reasons and exports PDF/JSON/evidence ZIP.
The printable target and capture guide support consistent framing. The
interactive evaluation page reads the committed report rather than demonstration
fixtures. Real proxy failures remain errors; saved fixtures require explicit
server-side DEMO_MODE=golden and retain demo provenance.

OpenCV 5 first-pass analysis uses checkerboard/contour evidence, sharpness,
contrast, specular masking, perspective and vertical-variation features. Eight
whitelisted tools support crop reinspection, reference comparison, edge
continuity, glare diagnostics, perspective rectification, vertical analysis,
crack-like feature extraction and across-frame analysis. Deterministic action
selection is the tested default; optional Gemini selects bounded tool arguments
with a finite timeout, one attempt and per-inspection permitted tools. No live
Gemini superiority is claimed.

For uncertain water, processing the same image cannot supply a new observation
or clear the sample. The controller requests a changed-lighting capture. A new
pair must be distinct, retain compatible aspect ratio, have sufficient detail,
acceptable translation, appearance correlation and overlap. The second image is
registered and evaluated in a common crop. If it remains ambiguous the result
stays REVIEW. This is appearance/translation consistency, not physical sample
identity verification or proof that a new camera exposure occurred.

The explicit water policy uses dimensionless visibility cutoffs (0.20 low and
0.55 high) with additional confounder checks. Crack-like widths are analysis
pixels; crack and FDM profiles are experimental. Uploaded analysis images are
bounded to 1024 pixels per side and overlays to 768. Resizing changes pixel
measurements, so no physical scale is inferred. Each inspection stores the actual
threshold/source snapshot and fingerprint; an altered policy rejects continuation
of an old capture session rather than silently reinterpreting it.

## Architecture and storage

See [the architecture diagram](../../reports/ARCHITECTURE.md).

Local SQLite retains captures/jobs with capacity bounds and expiry. Cloud mode
uses a private S3 bucket for jobs and atomic lossless PNG/session bundles. A fresh
adapter instance can retrieve all evidence without a process cache. Each object
has a payload hash, expiry metadata and server-side encryption; capture bundles
also verify decoded pixel hashes. Cloud errors return 503 instead of falling back
to memory. The optional legacy DynamoDB job adapter surfaces outages and rejects
oversized inline items; the primary deployment uses S3 to avoid that item limit.

Captures default to 30-minute access, jobs to 24 hours. Local cleanup occurs on
save/access; S3 lifecycle deletion is asynchronous. Server expiry is not an
exact-time erasure guarantee. Downloaded copies do not expire. Random result links
are bearer links, so recipients can access retained evidence during its lifetime.

Evidence ZIPs include analysis PNGs (not original upload bytes), optional
reference/second images, overlay, original result, policy snapshot, session
metadata and a file-byte SHA-256 manifest. Result frame hashes use decoded pixels
and shape instead; both bases are documented. Hashes expose modifications but do
not authenticate sensor provenance, capture time or ground truth. ZIP responses
above the 4 MB web budget return an explicit error rather than a broken download.

## AWS deployment preparation and current limits

[CloudFormation](../../infra/aws/template.yaml) targets Lambda ARM64 with private
encrypted S3, scoped object/bucket permissions, generated Secrets Manager backend
token, reserved concurrency two, seven-day logs and an error alarm. The Vercel
proxy forwards the token server-side. The script uses a clean committed revision,
ARM64 builder, ECR image digest and stack deployment; failures are not suppressed.

This environment has no AWS configuration/credential path or Vercel project token
available. The actual account deployment, ARM64 container execution, production
backend configuration and cloud cross-instance retrieval have **not** been
verified. CloudFormation lint and ARM64 binary-wheel dependency resolution pass;
neither establishes a running cloud system. AWS costs depend on the account and
traffic; no free-tier guarantee is made. COOL is not integrated.

## Reliability and resource protection

Requests are bounded to 4,000,000 bytes before multipart parsing, including
chunked bodies. Header-level PNG/JPEG/WebP dimensions are checked before OpenCV
decode; images above 25 megapixels are rejected. Uploads retain a combined web
budget and clear smaller-photo instructions. CPU-heavy work uses a thread pool,
with bounded admitted POST work and two inspection slots. Busy requests return
429 with Retry-After; liveness remains available. Reference/second-image errors
and storage failures must remain actionable rather than inventing a verdict.

Backend token protection, private no-store capture/archive responses, scoped
cloud permissions and TTL are implemented. This is a hackathon public-web path,
not a complete multi-tenant authentication/rate-limit system. A production service
would need a reviewed identity/abuse policy, monitoring destinations, account
budgets and an appropriate deletion/incident process.

## Evaluation

The paired manifest uses **34 generated binary-labeled primary fixtures**, five
generator-family groups and six supplied synthetic companion images. Six
ambiguous-label fixtures are excluded. No physical dataset or independent test
population is represented. Split validation rejects group/image leakage; declared
group provenance still needs human review.

| Strategy | Accuracy incl. abstentions | Coverage | Extra image inputs |
|---|---:|---:|---:|
| Single | 47.1% | 47.1% | 0 |
| Fixed capture | 64.7% | 64.7% | 6 |
| Exact-budget matched | 64.7% | 64.7% | 6 |
| Adaptive capture | 64.7% | 64.7% | 6 |

All available pairs are from uncertain cases, so the extra-capture strategies
choose the same six pairs. This is a tie, with no established adaptive advantage.
Zero false clears on these fixtures is not a safety guarantee. No confidence
interval, statistical significance, calibrated NTU/mm accuracy or real-world
impact is inferred. Strong fixed-processing/Gemini controls and an independent
physical blind set remain future evidence.

The [report](../../reports/evidence/2026-10-18-paired-capture-regression.json)
records per-case outcomes, image hashes, rejected pairs, exact requested-input
budgets, thresholds, source hashes and runtime versions. It measures image-input
allocation, not equal compute cost/time or acquisition authenticity. The old
run_experiments harness is retained only as a legacy diagnostic.

## Verification and reproduction

Run the backend tests and evaluator using [README instructions](../../README.md),
then frontend API tests/build and `npm run test:e2e`. Browser tests exercise a
real backend/production frontend on desktop/mobile: first upload, actual follow-up,
reload, evidence download, duplicate rejection, evaluation filtering/download,
and a controlled outage. S3 tests simulate a service contract with separate store
instances; they are not an AWS deployment test. The committed deployed-smoke
helper requires actual runtime architecture/shared storage/revision on a real URL.

Independent capture collection is documented [here](../../data/captures/README.md).
Remaining requirements and honest completion statuses are in the
[submission checklist](../../reports/SUBMISSION_CHECKLIST.md). No Devpost entry
or grant form was submitted by this agent. The official linked grant form
explicitly permits prize eligibility without a proposal or grant.
