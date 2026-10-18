# AWS deployment and verification

This configuration is prepared for account review and execution. It is not
evidence that an AWS deployment exists. Run commands from the repository root.

The architecture uses **Lambda ARM64 + private S3 shared storage** for both jobs
and capture sessions. This avoids DynamoDB's item-size limit for overlay-rich
results and reduces the number of services required for the demonstration.
The optional legacy DynamoDB job adapter remains supported, but the deployment
template uses S3. No COOL integration is claimed.

## Prerequisites

- AWS CLI v2 authenticated to the intended account and region, with permission
  to deploy the reviewed CloudFormation resources, access ECR, pass/create the
  scoped role and resolve the generated Secrets Manager token.
- Docker buildx with ARM64 execution support, or a native ARM64 builder. This
  development environment's current builder supports amd64 only; do not claim
  an ARM64 container test based on source import tests.
- Review account pricing, existing workloads and service quotas. Resources can
  incur charges. Reserved concurrency 2 bounds this function, but also requires
  account concurrency quota. The template adds private encrypted S3, one secret,
  seven-day logs and one CloudWatch alarm. No free-tier guarantee is made.
- A clean Git checkout and a stack name of at most 50 characters.

## Deploy

```bash
AWS_REGION=us-east-1 STACK_NAME=loopsight ./scripts/deploy_lambda.sh
```

The script checks identity, creates/reuses an ECR repository, builds an immutable
revision-tagged ARM64 image, resolves its digest, validates and deploys the
CloudFormation template, waits for completion and reports nonsecret outputs.
It fails on errors and does not overwrite an existing function's configuration
outside the stack. Use the same stack name for updates; choose a new name if
an earlier manually created Lambda has the same function name.

The generated backend token is stored in Secrets Manager and injected into the
Lambda environment using a dynamic reference. A permitted operator must set
the **same value** as Vercel's server-only `INFERENCE_API_TOKEN`, and set
`INFERENCE_API_URL` to `InferenceUrl`. Use secure project settings; never place
the token in a `NEXT_PUBLIC_` variable, Git, shell tracing or chat. The script
does not print token values. Redeploy Vercel after setting its environment.

Public `/health` and `/version` expose no secrets. Inspection, evidence and
readiness endpoints require the backend token when configured. The public
website proxies the token on the server. Public website traffic can still spend
compute; application concurrency bounds and Lambda reserved concurrency do not
replace account budgets or a production traffic/rate policy.

## Verify actual deployment

Run the deployed smoke helper through the website, using its HTTPS URL:

```bash
.venv/bin/python services/inference/scripts/smoke_deployed.py --web-base https://YOUR-PREVIEW.vercel.app --output /tmp/deployed-smoke.json
```

The helper requires an actual ARM64 backend, the expected revision and shared
S3 adapters; posts generated images through the web proxy; verifies recapture,
retained pixels, evidence manifest hashes and unknown/invalid request errors.
Use `--expected-revision` for the exact deployed commit. It does not establish
physical accuracy, external user impact or a cross-instance cold start by itself.
Different instance IDs across the retained capture flow are recorded if observed.
Prove separate-instance routing explicitly before claiming it as deployed evidence.

## Retention, links and cleanup

Capture access defaults to 30 minutes; job access defaults to 24 hours. The app
checks expiry before serving S3 objects. Bucket lifecycle removes stored objects
asynchronously after a day; this is not an exact-time deletion guarantee.
The bucket is private, blocks public ACLs/policies, requires TLS and encrypts
objects. Job links act as unguessable bearer links: recipients can view evidence
until expiry and keep downloaded copies afterward. Do not upload sensitive data.

Deleting the stack retains the evidence bucket to avoid accidental data loss;
the bucket can continue to incur storage charges until an authorized operator
empties/deletes it. ECR images are outside this stack and also require explicit
cleanup. Follow the account's approved cleanup/retention policy.
