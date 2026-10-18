# Competition rules recheck — 18 October 2026 (India time)

## Finding: no grant proposal is needed to remain prize-eligible

The actual grant form linked twice from the
[Devpost overview](https://opencv26.devpost.com/) now displays:

> Submissions for AWS Grants are closed. All teams, even those who were not
> selected or did not submit a proposal, are still eligible for all prizes!

Source: https://www.jotform.com/form/262145877145059 (HTTP 200 on this recheck).
This explicitly includes teams that never submitted a proposal. The earlier
advice to treat proposal submission as a prerequisite was wrong and is withdrawn.
No late grant application or proposal-receipt search is necessary to resolve
this particular prize-eligibility concern.

The official [grant announcement](https://opencv26.devpost.com/updates/46417-aws-compute-grant-notifications-have-been-sent)
also states that teams without a grant remain eligible for every prize, are
judged under exactly the same rubric by the same independent panel, and have
the same time to build. No grant-related judging penalty is stated.

This resolves the grant-proposal question. It does not certify an individual's
age/location/rights eligibility, private registration or a completed submission.
Registration is confirmed by the owner; no private account was accessed.

## Sources read and inconsistencies

The Devpost overview, full Rules page, Updates page, complete grant announcement,
linked closed grant form and OpenCV competition page were all retrieved
successfully on this recheck. Earlier access failures are no longer current.

| Issue | What the published sources say | Working action |
|---|---|---|
| Proposal prerequisite | OpenCV's general page still says to submit a grant proposal and refers to a required proposal. The linked form explicitly includes teams that **did not submit** as eligible for all prizes. The current Devpost Rules page does not impose a grant-proposal requirement. | Use the explicit clarification; continue without a grant proposal. |
| October 14 | Devpost's build section lists **October 7–14** for the grant-recipient Zoom check-in needed to receive the second half of the grant. | Do not treat this as the final-project deadline or as a check-in required of a team without a grant. The grant form is closed, but its exact closure date was not established. |
| Final deadline | The Devpost platform header says **October 26, 11:45 p.m. PDT**. Overview text and the announcement say **11:59 p.m. Pacific**. | Use the earlier platform cutoff: **October 27, 12:15 p.m. IST**; submit well before it. Do not rely on the extra 14 minutes. |
| Age | Devpost's overview widget says above legal age of majority; Rules text says at least 13 with guardian permission/forms where required. | An under-majority entrant needs platform/organizer clarification. Do not assume the more permissive statement resolves the conflict. |
| Team size | OpenCV's page contains both up-to-five wording and a no-more-than-four participation term. | If competing in a team, keep within four pending organizer confirmation. Current Devpost Rules text does not resolve the conflicting numerical limits. |
| Grant count | Overview summary says 50; prize listing/general OpenCV page say 55. | No effect on the no-grant build path; do not repeat an unqualified count. |

## Core build and entry requirements

From the current [Devpost overview](https://opencv26.devpost.com/) and
[Rules](https://opencv26.devpost.com/rules):

- OpenCV 5 must perform substantive image/video analysis.
- A meaningful project component must run on AWS; receiving a grant is optional.
- COOL and agentic methods are optional for Overall Awards.
- Code/data/models/media need the necessary rights and consent. Do not
  misrepresent capabilities, results, benchmarks or human review.
- Each team member must meet eligibility requirements; teams need an authorized
  representative. Applicable location, platform and third-party terms still apply.
- The entry must be safe, lawful and appropriate for public demonstration, with
  suitable privacy/security safeguards. Organizers may reject misleading,
  incomplete, unsafe or rules-violating entries.

## Final submission package

1. Technical report: problem, users, architecture, OpenCV 5, AWS deployment,
   evaluation, limitations and responsible use.
2. Public **or private judge-accessible** code repository/archive. Open source
   is not required.
3. Pinned dependencies and clear build/deployment/test instructions.
4. Architecture diagram showing OpenCV 5 and AWS, plus any agent/COOL components.
5. Working web endpoint **or arranged live screen-share demonstration**.
6. Public/unlisted judge-accessible video of **no more than five minutes**,
   showing the team, working application, architecture and main results.
7. Appropriate evaluation evidence, including failure cases/limitations.

The owner manages video/presentation; they remain required submission artifacts.

For **Agentic Vision**, show perception → decision/orchestration → action, an
actual trace where OpenCV output changes a later plan/tool/action/human request,
and evaluation of success, failure handling, observability and human control.
An explanation chatbot or coding-assistant use alone does not qualify.

For **Best Use of COOL**, COOL must execute the claimed core workload on AWS
Graviton or the Arm part of a documented hybrid system, with deployment/version
evidence and reproducible comparisons. LoopSight currently claims no COOL work.

## Judging

Overall weights: technical execution 30; innovation 20; real-world impact 20;
UX 10; **documentation and presentation together 10**; cloud delivery,
reproducibility and responsible operation 10. Grant selection is not a criterion.
At least two independent conflict-free scores are averaged. Technical execution,
then impact, are the first Overall tie-breakers.

Agentic weights: OpenCV+agent 30; orchestration/autonomy 25; effectiveness 20;
failure handling/observability/security/human control 15; UX/documentation/demo 10.
An entry may win at most one Overall Award and also one or both Special Awards.

For the owner's presentation-excluded engineering assessment, omit the combined
10-point documentation/presentation criterion and normalize the remaining
90 points. This is an internal planning assessment, not an official score.

## What happens next

No grant-proposal task blocks development. The next implementation priority is
shared AWS evidence/session storage and deployable configuration, followed by
actual deployment verification. Independent real captures and truthful grouped
evaluation remain essential. Confirm the private Devpost project is saved under
the intended registered account and team; submission itself is a later action.
No private dashboard, form submission or organizer message was performed here.
