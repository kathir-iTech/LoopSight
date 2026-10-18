#!/usr/bin/env bash
set -euo pipefail

# Reviewed CloudFormation deployment; requires authenticated AWS and an ARM64 builder.
# Does not print application tokens or modify Vercel settings.
cd "$(dirname "$0")/.."
command -v aws >/dev/null
command -v docker >/dev/null
command -v git >/dev/null
if [[ -n "$(git status --porcelain)" ]]; then
  echo "Commit or preserve pending changes before deploying an exact revision." >&2
  exit 1
fi
DEPLOY_REGION="${AWS_REGION:-${REGION:-us-east-1}}"
DEPLOY_STACK="${STACK_NAME:-loopsight}"
DEPLOY_REPO="${ECR_REPOSITORY:-loopsight-inference}"
if [[ ! "$DEPLOY_STACK" =~ ^[A-Za-z][A-Za-z0-9-]{0,49}$ ]]; then
  echo "STACK_NAME must begin with a letter and contain at most 50 letters, digits or hyphens." >&2
  exit 1
fi
DEPLOY_REVISION="$(git rev-parse HEAD)"
DEPLOY_ACCOUNT="$(aws sts get-caller-identity --query Account --output text --region "$DEPLOY_REGION")"
DEPLOY_REGISTRY="${DEPLOY_ACCOUNT}.dkr.ecr.${DEPLOY_REGION}.amazonaws.com"
DEPLOY_IMAGE="${DEPLOY_REGISTRY}/${DEPLOY_REPO}"
BUILDER_INFO="$(docker buildx inspect --bootstrap)"
if [[ "$BUILDER_INFO" != *"linux/arm64"* ]]; then
  echo "An ARM64 builder is required. No cloud resources have been created." >&2
  exit 1
fi
if ! aws ecr describe-repositories --repository-names "$DEPLOY_REPO" --region "$DEPLOY_REGION" >/dev/null 2>&1; then
  aws ecr create-repository --repository-name "$DEPLOY_REPO" --image-scanning-configuration scanOnPush=true --region "$DEPLOY_REGION" >/dev/null
fi
aws ecr get-login-password --region "$DEPLOY_REGION" | docker login --username AWS --password-stdin "$DEPLOY_REGISTRY"
docker buildx build --platform linux/arm64 --provenance=false \
  -f services/inference/Dockerfile.lambda -t "${DEPLOY_IMAGE}:${DEPLOY_REVISION}" --push .
DEPLOY_DIGEST="$(aws ecr describe-images --repository-name "$DEPLOY_REPO" --image-ids imageTag="$DEPLOY_REVISION" --query 'imageDetails[0].imageDigest' --output text --region "$DEPLOY_REGION")"
if [[ ! "$DEPLOY_DIGEST" =~ ^sha256:[a-f0-9]{64}$ ]]; then
  echo "Could not resolve an immutable image digest." >&2
  exit 1
fi
aws cloudformation validate-template --template-body file://infra/aws/template.yaml --region "$DEPLOY_REGION" >/dev/null
aws cloudformation deploy --template-file infra/aws/template.yaml --stack-name "$DEPLOY_STACK" \
  --capabilities CAPABILITY_IAM --region "$DEPLOY_REGION" --no-fail-on-empty-changeset \
  --parameter-overrides "ImageUri=${DEPLOY_IMAGE}@${DEPLOY_DIGEST}" "BuildRevision=${DEPLOY_REVISION}" "AllowedOrigin=${WEB_ORIGIN:-https://loopsight.vercel.app}"
aws cloudformation describe-stacks --stack-name "$DEPLOY_STACK" --region "$DEPLOY_REGION" --query 'Stacks[0].Outputs' --output table
printf '%s\n' "Configure Vercel server-only INFERENCE_API_URL and INFERENCE_API_TOKEN securely, redeploy, then run the deployed smoke helper. See infra/aws/README.md."
