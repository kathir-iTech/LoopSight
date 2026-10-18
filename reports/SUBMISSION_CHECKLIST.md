# Current submission checklist

Source: [verified current Devpost rules](COMPETITION_RULES_RECHECK.md), checked
18 October 2026. Prepared source is distinct from deployed verification.

## Prepared and locally checked

- [x] Substantive OpenCV 5 image analysis, bounded action selection and explicit policy.
- [x] First/follow-up evidence retention, pair validation and abstention behavior.
- [x] Shared S3 storage adapters, expiry enforcement and explicit outage errors.
- [x] Private encrypted bucket, scoped IAM, backend token, concurrency/log/alarm configuration.
- [x] Pinned Python runtime dependencies and npm lockfile; setup/deployment instructions.
- [x] [Architecture diagram](ARCHITECTURE.md) and [current technical report](../services/reports/technical_report.md).
- [x] [Devpost narrative draft](DEVPOST_SUBMISSION.md), reconciled with actual evidence.
- [x] Exact-budget paired evaluator, per-case regression report and website explorer.
- [x] Real capture guide and printable target; no generated images labeled physical.
- [x] Evidence ZIP with analysis images, policy snapshot, result and file hash manifest.
- [x] Backend/API tests, production build and desktop/mobile browser workflows.
- [x] Actual native ARM64 Lambda container build and handler smoke in GitHub CI.

## Required before final submission

- [ ] Confirm the private Devpost project, team and individual eligibility details.
- [ ] Execute reviewed AWS deployment in the intended account; verify its actual
  runtime/revision, authenticated web proxy and shared evidence storage. Native
  container testing is complete, but does not establish account deployment.
- [ ] Demonstrate meaningful AWS execution with real requests and retained
  evidence, plus actual deployment/log/cost identifiers. No hardcoded timings.
- [ ] Run the deployed smoke helper through the judge-accessible website.
- [ ] Record actual cross-instance retrieval if claiming deployed cold-worker durability.
- [ ] Collect and label independent physical capture groups; freeze blind splits
  before tuning and report failures/abstentions, without unsupported NTU claims.
- [ ] Update the report with physical results and measured latency/cost, or
  explicitly retain the limitations if evidence is unavailable.
- [ ] Make code/repository/archive accessible to judges (public is optional).
- [ ] Provide a working endpoint or arrange the permitted live screen-share.
- [ ] Owner records/uploads a judge-accessible video of at most five minutes.
- [ ] Reconcile final report, architecture, video and Devpost text with the exact
  deployed revision. Do not submit historical claims of certified physical units,
  100% effectiveness, measured Graviton speed or adaptive superiority.
- [ ] Submit before the earlier platform cutoff: 27 October 2026, 12:15 p.m. IST.

A grant proposal and grant selection are not prerequisites for prize eligibility.
COOL is optional and not claimed. For Agentic Vision, include the workflow diagram,
a real perception→action trace and effectiveness/failure/human-control evidence.
Other individual/platform eligibility requirements still apply.
