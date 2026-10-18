# Spending constraint update — 18 October 2026

**Superseding owner decision:** stop this OpenCV entry and all AWS setup;
preserve LoopSight for another suitable competition. The deployment gate stays
closed. AWS-specific tasks below are historical, not current instructions.
See [project direction and replacement-event criteria](PROJECT_DIRECTION.md).
The owner requires ₹0 spending during and after the competition and has no AWS
account. Earlier deployment authorization does not authorize chargeable resource
creation. The AWS deployment helper is now blocked before provider commands;
see [the zero-spend plan](ZERO_SPEND_PLAN.md). Actual AWS execution remains a
competition requirement and depends on verified no-charge access. Local work
can continue; no AWS resources have been provisioned in this session.

# LoopSight build progress and remaining evidence

Updated 18 October 2026. Presentation/video quality is excluded. This is the
current status record; the earlier strict review remains the baseline audit.

## Native ARM64 follow-up

The actual Lambda image now **builds and runs on a native ARM64 GitHub runner**.
The packaged handler passes `/version`, readiness, generated OpenCV inspection,
stored result retrieval and unknown-job checks through AWS's runtime emulator.
See [the successful job and recorded metadata](evidence/2026-10-18-native-arm64-lambda.json).
This supersedes earlier statements that ARM64 container execution was unverified;
actual AWS account deployment and shared cloud S3 execution remain unverified.
The native job also exports an exact-revision image archive so deployment from
this amd64 environment does not require a privileged emulator or ARM laptop.
Architecture/revision mismatch paths are covered by three deployment-script tests.

The Vercel CLI is installed outside the repository. Provider authentication
endpoints remain blocked and no AWS/Vercel credentials are present. Missing secure
connection fields and provider domains are saved in the environment draft; chat
permission alone does not authenticate either account.

## Website and cloud-storage build — previous batch

- Shared private **S3 job/capture adapters** are implemented with object/pixel
  hashes, expiry, encryption and no cloud-to-memory fallback. Separate-store
  contract tests pass; real AWS cross-instance verification is still outstanding.
- Local SQLite jobs are now authoritative and bounded (100 jobs / 128 MiB),
  with expiry and no stale RAM cache bypass. Capture bounds remain separate.
- CloudFormation/deploy script provide scoped storage permissions, generated
  backend token, ARM64 revision/digest, concurrency, logs and an alarm. The
  template passes cfn-lint 1.57.2; pinned Python 3.13 dependencies resolve to
  ARM64 wheels. The later native job above verifies container execution;
  AWS account deployment remains unverified.
- The website adds `/evaluation`, `/capture-guide`, a printable checkerboard,
  real backend/storage-read status and an evidence ZIP download. Mobile layout
  was inspected; a 412px viewport has no document overflow.
- Evidence archives preserve actual analysis images, policy/source snapshots,
  result and file manifests. Policy changes reject old recapture continuation.
  Uploads resize analysis images to at most 1024 pixels per side; overlays to 768.
- Body budgets apply before multipart parsing, dimensions before OpenCV decode,
  and inspection work is bounded/offloaded. Busy requests return retryable 429;
  corrupt references and wrongly typed identity fields are not silently ignored.
- Current checks: **119 backend passed / one optional live-Gemini skipped;
  17 web API tests; 8 desktop/mobile browser workflows; production build passed**.
  Production HTTP smoke verified evidence hashes, actual captures and correct
  errors. A separate backend-restart smoke verifies differing runtime IDs.

[Current technical report](../services/reports/technical_report.md),
[deployment instructions](../infra/aws/README.md) and
[submission checklist](SUBMISSION_CHECKLIST.md) describe the final scope.
Current S3 tests simulate the service contract; AWS credentials/configuration,
Vercel project token and independent physical data are still absent. Those
external prerequisites block live deployment and field validation, not the
implemented local website flow. Earlier stage counts/status below are historical.

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
   background deletion is not implemented; the cloud template configures asynchronous S3 lifecycle expiry.
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

Verification: **119 backend tests passed, one optional live-Gemini test skipped;
17 frontend API tests and eight desktop/mobile browser workflows passed; TypeScript and the production build passed.**
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
was accessible and confirms the weights below. The current Devpost Rules were subsequently read successfully; see the
[full recheck](COMPETITION_RULES_RECHECK.md). The official rubric combines
documentation and presentation in one 10-point criterion. For the owner's
presentation-excluded assessment, omit that whole criterion and normalize
the remaining 90 points. These are provisional engineering judgments,
not jury scores or winning probabilities, and use no private other-user projects.

| Criterion | Current evidence-based assessment |
|---|---:|
| Technical execution | 23/30 |
| Innovation | 11/20 |
| Real-world impact | 6/20 |
| Functional user experience | 8/10 |
| Combined documentation/presentation | Excluded at owner request |
| Responsible cloud delivery | 4/10 |
| **Technical subtotal / normalized assessment** | **52/90 ≈ 58/100** |

The strongest improvements are correctness, retained evidence and failure
handling. Independent effectiveness, real impact and verified cloud operation
still dominate the gap. A 95+ assessment is not supported by current evidence.

## Remaining work, in execution order

1. **Competition requirement resolved:** registration is owner-confirmed. The
   official linked grant form explicitly says teams that **did not submit a
   proposal** remain eligible for all prizes. No proposal task blocks building.
   See [the current rules recheck](COMPETITION_RULES_RECHECK.md). Final entry
   requirements and individual eligibility still apply; no private session or
   form submission was performed.
2. **AWS deployment verification:** shared S3 adapters, scoped infrastructure,
   expiry and explicit storage failures are implemented. Execute the reviewed
   deployment in the intended account, then prove uploads/retrieval across
   separate instances with actual runtime IDs and verify ARM64 image execution.
   Local SQLite does not share Lambda `/tmp`; source/adapter tests do not establish
   deployment. Configure the matching server-only backend token on Vercel.
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
6. **Operational validation:** decode/body/concurrency limits, explicit storage
   outages and pinned Python dependencies are implemented. Load-test the actual
   cloud deployment/cold starts and verify a real supported MCP client/transport.
   Current custom endpoint tests do not establish full client interoperability.
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
activate those changes. On the subsequent rules recheck, the Devpost overview,
Rules, Updates, grant announcement and linked grant form all returned HTTP 200.
Earlier public-page access failures are no longer current; authenticated account
access remains unverified.
