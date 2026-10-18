# Devpost narrative — evidence-aligned draft

Review with the final deployed revision before submission. AWS code is prepared;
AWS execution and independent physical outcomes are not yet verified.

## Project

**LoopSight — evidence-guided visual screening**

## Inspiration and intended users

An image inspection can fail because the camera lacks useful evidence: glare,
dim lighting, framing or an obscured reference pattern can make a confident
answer inappropriate. LoopSight explores a focused workflow for people doing
relative visual checks of a water sample: measure the image, explain uncertainty,
request a changed-lighting photo, and retain enough evidence to review the result.
It is not a drinking-water safety test or calibrated turbidity instrument.

## What it does

OpenCV 5 measures checkerboard visibility, contrast, sharpness, glare, perspective
and vertical variation. A bounded controller selects diagnostic tools; explicit
policy returns PASS, FAIL, REVIEW or NO_PATTERN_DETECTED. Same-image enhancement
cannot clear uncertain water. A follow-up must be distinct and pass appearance/
translation checks, after which the original first-pass evidence remains visible.

The website shows actual retained images, observation counts, provenance,
measured processing timings and a live backend/storage-read status. It exports
PDF/JSON and a ZIP containing images, a policy snapshot and a file hash manifest.
A capture guide provides a printable checkerboard. An evaluation explorer shows
all synthetic cases, including unresolved outcomes and control ties.

## How it is built

Next.js/React front end; FastAPI/OpenCV 5 inference; deterministic and optional
Gemini action selection; eight bounded image tools; SQLite locally and shared
private S3 objects in cloud mode. The prepared AWS CloudFormation stack targets
Lambda ARM64, encrypted evidence storage, scoped permissions, a generated backend
token, bounded concurrency, logs and an error alarm. AWS account deployment and
its actual performance remain to be verified.

## Evaluation and challenges

The committed data is generated synthetic regression material, not field data.
The corrected paired manifest contains 34 binary-labeled primary cases in five
generator-family groups, six companion images and six excluded ambiguous-label
fixtures. Single-image accuracy including abstentions is 47.1%; fixed, exact-budget
matched and adaptive capture tie at 64.7%, with six extra inputs each. This dataset
does not demonstrate adaptive allocation superiority or physical accuracy.

We removed an unvalidated NTU mapping and an assumed millimetre scale. We also
replaced successful-looking fixtures on backend failure with honest errors,
persisted original captures across workers, bounded input/tool work and tested
storage outages, policy changes, duplicate captures and evidence expiry.

## What remains

Verify the actual AWS/Vercel deployment; collect independent grouped physical
captures and blind labels; measure real false-clear/coverage tradeoffs, latency,
cost and user outcomes. Experimental crack/FDM profiles remain secondary. No
COOL integration, calibrated confidence, structural certification, water safety
certification or competition score is claimed.

## Award path

Agentic Vision: image evidence changes a diagnostic tool or a human recapture
request, followed by deterministic evaluation of the new evidence. Include actual
traces, failure cases and human-control behavior. Using a coding assistant alone
is not the project's agentic contribution.
