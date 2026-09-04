#!/usr/bin/env bash
set -euo pipefail

# LoopSight — one-pass Lambda deploy (scripted, ready for credentials)
# Follows services/inference/README_DEPLOY_LAMBDA.md exactly.
# Prereqs: AWS CLI v2 configured (aws configure / SSO), Docker + buildx, region set.
# Usage:
#   chmod +x scripts/deploy_lambda.sh
#   REGION=us-east-1 REPO=loopsight-inference FUNCTION=loopsight-inference ./scripts/deploy_lambda.sh
# Owner does IAM/account/billing-alarm steps manually first when prompted.

REGION="${REGION:-us-east-1}"
REPO="${REPO:-loopsight-inference}"
FUNCTION="${FUNCTION:-loopsight-inference}"
ACCOUNT_ID="${ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "REPLACE_WITH_ACCOUNT_ID")}"
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPO}"

echo "== LoopSight Lambda deploy =="
echo "Region: ${REGION}"
echo "Repo:   ${REPO}"
echo "Func:   ${FUNCTION}"
echo "ECR:    ${ECR_URI}"
echo ""

if [[ "${ACCOUNT_ID}" == "REPLACE_WITH_ACCOUNT_ID" ]]; then
  echo "!! Could not resolve ACCOUNT_ID. Set ACCOUNT_ID env or run aws configure first."
  exit 1
fi

echo "[0/5] Billing tripwire reminder: create CloudWatch billing alarm at \$1 before proceeding."
echo "     Console → CloudWatch → Billing → Create alarm at 1 USD (tripwire)."
read -p "Press Enter to continue (or Ctrl+C to abort): " _

echo "[1/5] Creating ECR repo ${REPO} (if not exists)..."
aws ecr create-repository --repository-name "${REPO}" --image-scanning-configuration scanOnPush=false --region "${REGION}" 2>/dev/null || echo "  ECR repo already exists or creation skipped."

echo "[1b] Logging into ECR..."
aws ecr get-login-password --region "${REGION}" | docker login --username AWS --password-stdin "${ECR_URI%/*}"

echo "[2/5] Building arm64 image and pushing to ${ECR_URI}:latest ..."
docker buildx build --platform linux/arm64 \
  -f services/inference/Dockerfile.lambda \
  -t "${ECR_URI}:latest" \
  --push .

echo "[2b] Verifying image in ECR..."
aws ecr describe-images --repository-name "${REPO}" --region "${REGION}" --query 'imageDetails[0].imageTags' 2>&1 | head

echo "[3/5] Creating IAM role ${FUNCTION}-role if needed..."
aws iam create-role --role-name "${FUNCTION}-role" \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}' 2>/dev/null || echo "  IAM role already exists."
aws iam attach-role-policy --role-name "${FUNCTION}-role" --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole 2>&1 | head
echo "  Waiting 5s for IAM propagation..."
sleep 5

echo "[3b] DynamoDB table loopsight-jobs (PAY_PER_REQUEST, optional)..."
aws dynamodb create-table --table-name loopsight-jobs --attribute-definitions AttributeName=job_id,AttributeType=S --key-schema AttributeName=job_id,KeyType=HASH --billing-mode PAY_PER_REQUEST --region "${REGION}" 2>/dev/null || echo "  Table already exists or skipped."

echo "[4/5] Creating Lambda function ${FUNCTION} from image..."
aws lambda create-function \
  --function-name "${FUNCTION}" \
  --package-type Image \
  --code ImageUri="${ECR_URI}:latest" \
  --role "arn:aws:iam::${ACCOUNT_ID}:role/${FUNCTION}-role" \
  --architectures arm64 \
  --memory 1024 \
  --timeout 30 \
  --environment Variables="{DYNAMO_TABLE_NAME=loopsight-jobs,GEMINI_API_KEY=}" \
  --region "${REGION}" 2>&1 | tail -20 || echo "  Function may already exist — will try update..."

echo "[4b] Updating function code (if already exists)..."
aws lambda update-function-code --function-name "${FUNCTION}" --image-uri "${ECR_URI}:latest" --region "${REGION}" 2>&1 | tail -10 || true
aws lambda wait function-updated --function-name "${FUNCTION}" --region "${REGION}" 2>&1 | tail
aws lambda update-function-configuration --function-name "${FUNCTION}" --environment Variables="{DYNAMO_TABLE_NAME=loopsight-jobs,GEMINI_API_KEY=}" --region "${REGION}" 2>&1 | tail -10 || true

echo "[5/5] Creating Function URL (no API Gateway)..."
aws lambda create-function-url-config --function-name "${FUNCTION}" --auth-type NONE --region "${REGION}" 2>&1 | tail -20 || echo "  URL already exists."
aws lambda add-permission --function-name "${FUNCTION}" --statement-id FunctionURLAllowPublicAccess --action lambda:InvokeFunctionUrl --principal '*' --function-url-auth-type NONE --region "${REGION}" 2>&1 | tail -5 || echo "  Permission already exists."

FUNC_URL=$(aws lambda get-function-url-config --function-name "${FUNCTION}" --region "${REGION}" --query 'FunctionUrl' --output text 2>/dev/null || echo "")
echo ""
echo "== Done =="
if [[ -n "${FUNC_URL}" ]]; then
  echo "Function URL: ${FUNC_URL}"
  echo "Next: set in Vercel → Project → Settings → Environment Variables:"
  echo "  INFERENCE_API_URL=${FUNC_URL%/}"
  echo ""
  echo "Test:"
  echo "  curl -s ${FUNC_URL}health"
  echo "  curl -s -X POST -F \"image=@/path/to/glass.jpg\" -F \"inspection_profile=water_turbidity_v1\" ${FUNC_URL}inspect"
else
  echo "Could not fetch FunctionUrl — check 'aws lambda get-function-url-config' manually."
fi
echo ""
echo "Cleanup when done: see README_DEPLOY_LAMBDA.md Cleanup section."
