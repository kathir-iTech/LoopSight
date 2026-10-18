# Zero-spend constraint — 18 October 2026

The owner has no AWS account and requires ₹0 out-of-pocket spending during the
competition and afterward. This overrides earlier broad deployment authorization.
The owner subsequently agreed to provide a card privately if needed for signup;
the ₹0 constraint remains in force. Card entry does not authorize a paid plan,
verification debit, subscription, upgrade or chargeable resource deployment.
Do not request card details in chat or provision resources under the earlier
broad authorization. Confirm current signup terms before recommending card entry.

## Verified competition requirements

The [official overview](https://opencv26.devpost.com/), retrieved on this date,
says every entry must perform substantive OpenCV 5 image/video analysis and
"run a meaningful component on AWS."

Its **Free AWS Credits for New Members** section says new customers may receive
$100 in credits on a Free Plan and earn up to $100 more, subject to current AWS
terms, service availability and expiration rules. This is a credit offer, not
evidence of perpetual free hosting or of a card-free signup route.

The [linked grant form](https://www.jotform.com/form/262145877145059) is closed
and explicitly says teams that did not submit a proposal remain eligible for
all prizes. This does not waive the meaningful-AWS-component requirement.

AWS's Free Tier and FAQ pages returned proxy CONNECT 403 in this environment.
Current payment verification, possible card authorization holds, Free Plan
expiry/upgrade behavior and exact service coverage have **not** been verified
here. Do not present assumptions about those terms as checked facts.

## Deployment controls and remaining dependency

- No AWS resources have been deployed by this session. Account access remains
  unavailable. Native ARM64 container CI is not an AWS account deployment.
- `infra/aws/ZERO_SPEND_ONLY` blocks `scripts/deploy_lambda.sh` before provider
  commands. A regression test verifies that no AWS, Docker or Git command runs.
  Other scripts, consoles and existing cloud resources are outside that gate.
- The prepared template can incur ECR, S3, Secrets Manager, Lambda and CloudWatch
  charges. Retained S3/ECR resources can continue to cost money after stack
  deletion. Budget alerts and concurrency limits are not hard billing caps.
- Continue local development, deterministic inference, synthetic evaluation and
  existing tests without provisioning services or enabling paid features.
  Local software can remain usable independently of hosted free-tier offers.
- A verified organizer-managed, no-charge AWS environment could resolve the
  deployment dependency if offered and compatible. Availability is unconfirmed.
  Inspect its terms, permitted services, expiry, ownership and cleanup before
  revising the gate or connecting credentials. No organizer message has been sent.
- Without actual permitted AWS execution, a local/Vercel-only demonstration does
  not satisfy the published AWS requirement. Do not describe it as compliant.
  No hosting plan is promised to stay free forever.

## Prepared organizer question — not sent

> I am registered for the OpenCV AI Competition 2026 and building LoopSight.
> I have no AWS account and cannot incur any charge or later billing liability.
> Is an organizer-managed, card-free AWS sandbox
> available for a meaningful project component? If so, please confirm permitted
> services, expiry and that no payment method or billing liability is required
> from me. If unavailable, is there an explicitly approved alternative that
> satisfies the AWS requirement? I understand the grant application is closed.

Do not send this message without an explicit instruction to contact organizers.

## Owner-assisted signup next step

The owner can inspect the official [AWS Free Tier page](https://aws.amazon.com/free/)
and its account-plan selection privately. Before payment entry, collect the
non-sensitive plan/billing text for review. Do not choose a Paid Plan, a paid
support subscription, or accept a verification charge under the zero-spend
constraint. Check any bank authorization/foreign-exchange terms as well.

The latest retry of the Free Tier, FAQ, account-plan and account-management
documentation still returned proxy CONNECT 403. A saved allowlist is not proof
that runtime access is active. No current Free Plan billing protection or
service compatibility has been verified and the deployment gate remains closed.
