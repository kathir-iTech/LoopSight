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

The owner has now signed in with GitHub and supplied an AWS Settings profile
screenshot (`settings.aws.com/profile`). No card has been added, owner-confirmed.
The screenshot establishes browser sign-in, not this workspace's deployment
permissions or the account's actual plan. Inspect **Billing** in that sidebar
and share only non-sensitive plan/credit information. Do not upgrade, activate
advanced features, add paid support or enter payment details for this check.

## Successful official-terms recheck after signup

The following official pages subsequently became accessible (HTTP 200). This
supersedes the earlier documentation access failures; it does not authenticate
the owner's account:

- [AWS Free Tier FAQ](https://aws.amazon.com/free/free-tier-faqs/), General Q4:
  "A payment method isn't required to sign up for most new customers." Some
  customers may be asked for one for identity verification. The FAQ describes
  a new signup experience launched in October 2026, automatic Free Plan enrollment
  for eligible new accounts, and Billing in the Settings Portal.
- [Choosing a plan](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html):
  "The Free account plan ensures you won't incur any charges while you explore
  AWS services and build your applications." The comparison table states
  "No charges incur during usage." A Free Plan ends after six months or credit
  exhaustion, whichever is first; access closes rather than automatically
  becoming a Paid Plan. AWS retains content for 90 days before deletion.
- The FAQ likewise states the Free Plan account and projects are suspended at
  expiry and describes upgrading as optional. Its Paid Plan can bill beyond
  credits; paid project spend limits start at $20 and do not meet a ₹0 policy.
- [AWS Builder ID sign-in](https://docs.aws.amazon.com/signin/latest/userguide/sign-in-builder-id.html)
  supports GitHub login and distinguishes Builder ID from AWS resource-account
  credentials. GitHub login alone does not establish deployment access. Do not
  assume which identity/account type the profile represents from the screenshot.

A confirmed Free Plan may therefore provide the required no-charge AWS route;
an organizer sandbox is an alternative, not the only possible route. Exact
service availability and the owner's plan still need verification. Do not
upgrade or activate advanced features to make the prepared template work.
Keep an offline export before expiry; no perpetual free cloud hosting is promised.

Read-only connection discovery found no AWS access keys, web-identity/container
credentials or populated shared credential/config profiles. The project Python
SDK's session lookup returned `ProfileNotFound`; no authenticated API request
was possible. No profile values, credentials or payment details were printed.
No resources were created. The deployment gate remains closed pending actual
plan, service compatibility and secure authentication verification.
