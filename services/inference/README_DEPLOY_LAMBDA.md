# LoopSight Inference — Lambda Deployment (ARM64, Always-Free Tier)

This image packages the **same** FastAPI app that runs locally via `uvicorn main:app` — no code fork.
It runs on **AWS Lambda (ARM64)** via `Mangum`, not on a Graviton EC2 instance and **not** with COOL.
COOL requires a paid Marketplace AMI + `m8g.4xlarge` (not free-tier eligible) — this project intentionally does **not** pursue Best Use of COOL. The target awards are Overall + Agentic Vision; Lambda's always-free tier (`1M` requests + `400,000 GB-seconds` per month, forever, non-expiring) comfortably covers hackathon demo volumes (dozens–hundreds of requests) at **$0**.

> **Billing tripwire (do this first, regardless of free tier):** in the AWS Console → CloudWatch → Billing → Create alarm at **$1**. This is not a budget — it's a tripwire so any accidental free-tier exceedance is visible immediately.

---

## Prereqs

- AWS account, AWS CLI v2 configured (`aws configure` or SSO), Docker + `docker buildx` available.
- Region choice: e.g. `us-east-1` (Lambda free tier applies in all regions; pick one and keep it consistent).
- No Gemini key or Dynamo table is required to deploy — both are optional and the service falls back gracefully when unset/unreachable.

---

## 1. Create an ECR repository (once per region)

> **ECR note:** ECR is **not** confirmed to be part of AWS's permanent *Always Free* service list (Lambda's free tier is — API Gateway's is not, which is why this guide avoids it). The image is ~400–600 MB and at demo push frequency any charge would be negligible (pennies), but if provably-zero spend matters, a **.zip-based Lambda deployment using a prebuilt Lambda Layer for `opencv-python-headless`** is a documented alternative that avoids ECR entirely — noted here as an option, not implemented now.

ECR storage beyond the free credit is pay-per-GB-month but at this project's image size and demo scale you never push frequently enough to exceed a few cents.

```bash
aws ecr create-repository \
  --repository-name loopsight-inference \
  --image-scanning-configuration scanOnPush=false \
  --region us-east-1
```

Note the `repositoryUri` from the output, e.g. `123456789012.dkr.ecr.us-east-1.amazonaws.com/loopsight-inference`.

---

## 2. Build and push the ARM64 image

The Lambda base image is **multi-arch** but Lambda itself must receive an `arm64` image — build explicitly for that platform. Building and pushing is a local Docker operation; no AWS charge beyond ECR storage (negligible at ~300–500 MB, free-tier covered).

From the **repository root** (so `requirements.txt` is visible to the Dockerfile):

```bash
# One-time: enable buildx and login to ECR
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-east-1.amazonaws.com

# Build for arm64 and push in one step (requires docker buildx)
docker buildx build --platform linux/arm64 \
  -f services/inference/Dockerfile.lambda \
  -t 123456789012.dkr.ecr.us-east-1.amazonaws.com/loopsight-inference:latest \
  --push .
```

**If you prefer building from `services/inference` as context**, first copy the root `requirements.txt` into that dir or adjust the `COPY` lines in `Dockerfile.lambda` — the default Dockerfile assumes **repo-root context** as shown above.

Verify in ECR:

```bash
aws ecr describe-images --repository-name loopsight-inference --region us-east-1
```

---

## 3. Create the Lambda function from the image

**Cost-relevant settings — each stays inside free tier at demo volume:**

- `--architectures arm64` — Lambda runs on Graviton (ARM64) under the hood; no EC2 hourly rate.
- `--memory 1024` (MB) — 1 GB; Lambda free tier is **400,000 GB-seconds/month**. At 1 GB, that's ~400k seconds of execution per month. A demo request takes ~0.3–1.0 s, so even 1,000 requests ≈ 500–1,000 GB-seconds — orders of magnitude below the limit. Larger memory also gives more CPU, so 1024 MB is a good cost/latency trade-off and still essentially free at this scale.
- `--timeout 30` (seconds) — per-request ceiling; the handler itself is fast (<2 s typical). A 30 s timeout prevents runaway invocations from burning GB-seconds, without affecting normal requests.

```bash
# Create an IAM role for Lambda if you don't have one (least-privilege, logs only):
aws iam create-role --role-name loopsight-lambda-role \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}'

aws iam attach-role-policy --role-name loopsight-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# Wait a few seconds for IAM propagation, then create the function:
aws lambda create-function \
  --function-name loopsight-inference \
  --package-type Image \
  --code ImageUri=123456789012.dkr.ecr.us-east-1.amazonaws.com/loopsight-inference:latest \
  --role arn:aws:iam::123456789012:role/loopsight-lambda-role \
  --architectures arm64 \
  --memory 1024 \
  --timeout 30 \
  --environment Variables="{GEMINI_API_KEY=,DYNAMO_TABLE_NAME=}" \
  --region us-east-1
```

**To use DynamoDB persistence** (optional, not required for demo): create a table first, then update the function env:

```bash
aws dynamodb create-table \
  --table-name loopsight-jobs \
  --attribute-definitions AttributeName=job_id,AttributeType=S \
  --key-schema AttributeName=job_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
# PAY_PER_REQUEST is free-tier eligible; at demo write volumes (hundreds of items) it's $0.

aws lambda update-function-configuration \
  --function-name loopsight-inference \
  --environment Variables="{DYNAMO_TABLE_NAME=loopsight-jobs,GEMINI_API_KEY=}" \
  --region us-east-1
```

**To enable real Gemini tool selection** (optional): set the key as an env var (or better, Secrets Manager — env var shown for brevity):

```bash
aws lambda update-function-configuration \
  --function-name loopsight-inference \
  --environment Variables="{GEMINI_API_KEY=YOUR_KEY_HERE}" \
  --region us-east-1
```

If `GEMINI_API_KEY` is empty/unset, the service automatically uses the deterministic mock fixture — identical to local dev without a key.

Update the image after code changes:

```bash
docker buildx build --platform linux/arm64 -f services/inference/Dockerfile.lambda -t 123456789012.dkr.ecr.us-east-1.amazonaws.com/loopsight-inference:latest --push .
aws lambda update-function-code --function-name loopsight-inference --image-uri 123456789012.dkr.ecr.us-east-1.amazonaws.com/loopsight-inference:latest --region us-east-1
```

---

## 4. Expose via Lambda Function URL (no API Gateway)

API Gateway's free-tier status for AWS accounts created **after July 15, 2025** is genuinely unconfirmed — most current pricing guides describe it as the old "1M calls free for 12 months" tier, which does not apply to a newly-created account (it draws from the general $100–200 signup credit instead, and charges from the first call once that's gone). Zero spend is a hard constraint here, so this guide sidesteps the question entirely: **Lambda Function URLs** are a built-in Lambda feature — a direct HTTPS endpoint for the function with **no separate service and no charge beyond standard Lambda invocations**, which *are* confirmed always-free regardless of account age (`1M` requests + `400,000 GB-seconds`/month, forever — see Section 1 header).

Lambda Function URLs give one less moving part and remove the uncertain cost entirely instead of hoping it stays under a limit.

```bash
# Create a public Function URL (no auth — suitable for a hackathon demo; add auth via --auth-type AWS_IAM if needed)
aws lambda create-function-url-config \
  --function-name loopsight-inference \
  --auth-type NONE \
  --region us-east-1
# Note the FunctionUrl from output, e.g. https://abc123.lambda-url.us-east-1.on.aws/

# Allow public invocation of the URL (required once)
aws lambda add-permission \
  --function-name loopsight-inference \
  --statement-id FunctionURLAllowPublicAccess \
  --action lambda:InvokeFunctionUrl \
  --principal '*' \
  --function-url-auth-type NONE \
  --region us-east-1
```

Test the deployed service (replace `<function-url>`):

```bash
curl -s https://<function-url-id>.lambda-url.us-east-1.on.aws/health
curl -s -X POST -F "image=@/path/to/print.jpg" -F "inspection_profile=fdm_print_surface_v1" https://<function-url-id>.lambda-url.us-east-1.on.aws/inspect
```

---

## 5. Wire Vercel

In Vercel → Project → Settings → Environment Variables, set the **Function URL** directly (no API Gateway):

```
INFERENCE_API_URL=https://<function-url-id>.lambda-url.us-east-1.on.aws
```

For example, after `create-function-url-config` the CLI returns `FunctionUrl: https://abc123xyz.lambda-url.us-east-1.on.aws/` — paste that value (without trailing slash) as `INFERENCE_API_URL`.

The Next.js routes (`apps/web/src/app/api/inspect/route.ts`, `apps/web/src/app/api/jobs/[id]/route.ts`) proxy to this URL and **fall back to mock data with a `console.warn`** if the Lambda is unreachable, so the deployed demo never shows a 502 — it just serves the canned `MOCK_RESULT`.

---

## Local run (unchanged, still works with no AWS/Gemini setup)

```bash
# Terminal 1 — inference (no env vars needed)
uvicorn main:app --reload --port 8000  # from services/inference

# Terminal 2 — frontend
npm run dev  # from apps/web (defaults to http://localhost:8000)
```

No `GEMINI_API_KEY` and no `DYNAMO_TABLE_NAME`/AWS credentials → the service uses `InMemoryJobStore` and the mock Gemini fixture — identical to production fallback.

---

## Notes

- **This image is meant to run as a Lambda container**, not as a generic `docker run` elsewhere. Locally `docker run -p 8000:8000 --env-file .env <image>` will start, but Lambda's runtime interface is different; the intended local dev loop remains `uvicorn main:app`.
- **Image size:** the Lambda Python base + `opencv-python-headless` is ~400–600 MB — within ECR free tier at low push frequency. No COOL layer is present or needed.
- **Concurrency:** defaults to 1,000 concurrent executions (account limit); demo traffic never approaches this.

## Cleanup (avoid any surprise)

```bash
# Function URL is deleted automatically with the function; no separate API Gateway resource to delete
aws lambda delete-function-url-config --function-name loopsight-inference --region us-east-1  # optional — deleted with function anyway
aws lambda delete-function --function-name loopsight-inference --region us-east-1
aws ecr delete-repository --repository-name loopsight-inference --force --region us-east-1
aws dynamodb delete-table --table-name loopsight-jobs --region us-east-1  # if created
aws iam detach-role-policy --role-name loopsight-lambda-role --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
aws iam delete-role --role-name loopsight-lambda-role
```

