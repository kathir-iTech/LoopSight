# LoopSight build progress and remaining evidence

Updated 18 October 2026. Presentation/video quality is excluded. This is the
current status record; the earlier strict review remains the baseline audit.

## Implemented and checked

1. **Trustworthy inference:** unknown jobs return 404; unavailable backends stay
   errors. Fixtures require explicit server-side demo mode. Results retain
   execution provenance. Lambda source packaging and tool bounds were repaired.
2. **Image measurements:** removed the unvalidated NTU formula, WHO tiers and
   assumed millimetre scale from runtime results and UI. Crack width uses analysis
   pixels; water visibility is dimensionless. A versioned measurement contract
   accompanies JSON/PDF results. Confidence labels remain heuristic.
3. **Real recapture:** lossless first/reference/second analysis frames, hashes,
   original timestamp and profile survive workers sharing a SQLite file. Sessions
   expire after 30 minutes by default, retain at most 100 entries and enforce
   per-entry/total encoded-image limits. Cleanup occurs on access/save; exact-time
   background deletion and cloud lifecycle policies are not implemented.
4. **Pair checks and abstention:** reject duplicate, poorly aligned, unrelated or
   incompatible-aspect captures. Register translations, measure a common crop,
   and retain original first-pass evidence. Same-image water enhancement cannot
   clear an uncertain sample. New captures that remain ambiguous stay REVIEW.
   Visual agreement does not certify identity or prove a photo was newly taken.
5. **Evidence UI:** actual retained first/second images, expiry/instructions,
   observation counts and recapture failures are visible. Missing images are not
   replaced by generic checkerboards. Raw capture responses are private/no-store.
   Runtime architecture/instance information is available through `/api/version`.
6. **Fair evaluator:** paired-image manifests enforce split/group/image leakage
   checks. Matched and adaptive strategies receive exactly equal requested-image
   budgets. Reports separate abstention, coverage, false-clear rate, rejected
   pairs and actual inputs, with source hashes/thresholds/runtime versions.

Verification: **97 backend tests passed, one optional live-Gemini test skipped;
12 frontend API tests passed; TypeScript and the production build passed.**
Two upstream deprecation warnings remain. A production-server smoke verified a
new backend runtime instance between first upload and follow-up, unchanged first
measurements, both capture images pixel-identical after retrieval, duplicate=422,
unknown job=404 and home=200. This is local synthetic transport evidence, not
field accuracy or an AWS cold-start test.

## Current evaluation result

The [committed report](evidence/2026-10-18-paired-capture-regression.json) uses 34
generated binary-labeled primary fixtures in five generator-family groups.
Six ambiguous-label fixtures are excluded; six synthetic companion images exist.
No physical dataset is represented.

| Strategy | Accuracy including abstentions | Coverage | Extra inputs |
|---|---:|---:|---:|
| Single image | 47.1% | 47.1% | 0 |
| Fixed capture when available | 64.7% | 64.7% | 6 |
| Exact-budget matched capture | 64.7% | 64.7% | 6 |
| Adaptive capture | 64.7% | 64.7% | 6 |

All available pairs belong to ambiguous cases, so these controls choose the same
six pairs. **There is no demonstrated adaptive allocation advantage.** Neither
synthetic labels nor zero false clears on this small fixture set establish
physical validity, significance, safety or field performance. The historical
100% C / +0.7500 claim used a different, flawed diagnostic and is withdrawn as
current comparative evidence. More REVIEW outcomes reflect abstention instead
of silently clearing images after enhancement.

## Strict working assessment

The official [OpenCV overview](https://opencv.org/opencv-ai-competition-2026/)
was accessible and confirms the weights below. Documentation is a technical
report/reproducibility criterion here; visual presentation and video are not
scored. Devpost's governing rules remain inaccessible, so eligibility and any
differences must be checked there. These are provisional engineering judgments,
not jury scores or winning probabilities, and use no private other-user projects.

| Criterion | Current evidence-based assessment |
|---|---:|
| Technical execution | 23/30 |
| Innovation | 11/20 |
| Real-world impact | 6/20 |
| Functional user experience | 8/10 |
| Technical documentation/reproducibility | 7/10 |
| Responsible cloud delivery | 4/10 |
| **Working total** | **59/100** |

The strongest improvements are correctness, retained evidence and failure
handling. Independent effectiveness, real impact and verified cloud operation
still dominate the gap. A 95+ assessment is not supported by current evidence.

## Remaining work, in execution order

1. **Competition requirement:** registration is owner-confirmed; proposal receipt
   is not. The official overview explicitly requires the grant proposal, while
   grant selection is not required for prizes. See
   [proposal status and review draft](PROPOSAL_STATUS_AND_DRAFT.md). No form was
   submitted or private Devpost session accessed.
2. **AWS persistence and deployment:** implement shared session/capture storage
   (private objects plus metadata), scoped IAM and expiry/deletion. Local SQLite
   does not share `/tmp` between Lambda instances. Surface DynamoDB failures and
   remove reliance on in-memory fallback for durable success. Prove uploads and
   retrieval across separate instances with actual runtime IDs. Verify ARM64
   image execution; source packaging tests do not establish it.
3. **Vercel production:** GitHub deployment records show a Vercel integration,
   with previews for this branch. Public production still serves older code:
   an unknown job returned HTTP 200/PASS without provenance during this audit.
   No updated backend endpoint or Vercel configuration is verified. Merge only
   with a working real-inference configuration and deployed smoke evidence.
4. **Physical data:** collect independent preparations, phones, sessions and
   genuine capture pairs for easy and difficult cases using the
   [collection protocol](../data/captures/README.md). Freeze grouped splits and
   labels before tuning. Physical NTU stays disabled without reference readings
   and independent calibration; physical crack units need a scale reference.
5. **Fair effectiveness study:** add strong fixed-processing and optional
   Gemini controls, a frozen blind set, group-aware uncertainty intervals,
   false-clear analysis and measured observation/latency/cost tradeoffs. Report
   ties, losses, exclusions and failed recaptures. Never tune on the blind test.
6. **Operational hardening:** bound decode/body/concurrency work, handle storage
   outages consistently, test load and cloud cold starts, lock Python deployment
   dependencies, and verify a real supported MCP client/transport. Current MCP
   endpoint tests do not establish full client interoperability.
7. **User/field validation:** mobile camera permissions, interrupted uploads,
   task completion, capture retries and interpretation of REVIEW/scope. Record
   real user observations and outcome evidence rather than assume impact.
8. **Submission freeze:** reconcile historical documents, actual AWS/version/
   cost evidence and final technical report. Owner manages presentation/video.

No AWS credentials/configuration or Vercel project token/binding were available
in this machine. GitHub read/push works; secret-list permission is restricted.
The Windows Claude export cited by the owner is not present in this cloud
workspace. The repository handover was read but contains unsupported historical
claims. Credentials should be configured through secure settings, not chat.

## Official-source and setup notes

The OpenCV overview requires substantive OpenCV 5 processing and meaningful AWS
use. Its Agentic Vision rubric separately weighs OpenCV+agent (30), orchestration
(25), effectiveness (20), failure/human control (15), and UX (10). A controller
must demonstrate visual evidence changing a later action; coding-assistant use
alone is not that contribution. COOL integration has not been implemented.

Environment setup/start instructions and required public-source domains are
saved as a draft. Draft saving does not apply network access or publish the
environment. The owner must review/save and publish in environment settings to
activate those changes. The running proxy still blocks the Devpost profile and
proposal form; remote Devpost event protection also blocks rules retrieval.
