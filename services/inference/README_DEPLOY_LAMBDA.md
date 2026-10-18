# Lambda deployment

Use [the current deployment guide](../../infra/aws/README.md) and reviewed
[CloudFormation template](../../infra/aws/template.yaml).

The former manual deployment script omitted durable cross-instance capture
storage and sufficient data permissions, suppressed failures and made unsupported
free-tier claims. It is superseded by the stack-based deployment. No deployment
is established by documentation or source packaging tests alone.
