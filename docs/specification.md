# AI Bug Report Classifier Specification

## A. Project overview

### What the system does
The AI Bug Report Classifier is a service that accepts unstructured natural-language bug reports and converts them into a validated structured classification result. The system is intended to help teams turn noisy issue descriptions into a consistent, machine-readable format that can be triaged, prioritized, and reviewed.

### What problem it solves
Bug reports are often inconsistent, incomplete, and written in different styles across users, customers, QA teams, and internal stakeholders. Without structure, teams struggle to:

- understand the actual problem quickly
- compare issues across channels
- assign priority and severity consistently
- identify whether a bug is reproducible
- determine when a report needs human review

This system aims to reduce manual triage effort while preserving safety checks for uncertain or incomplete input.

### Who would use it
The primary users are likely:

- engineering teams triaging incoming bug reports
- support or customer success teams routing issues to the right owners
- QA and release managers reviewing classifications and risk
- operations teams monitoring defect trends and escalation patterns

The system is a decision-support tool, not a replacement for engineering judgment.

### Why structured bug reports are useful
Structured outputs make it easier to:

- classify bugs into a consistent taxonomy
- prioritize work based on severity and business impact
- analyze patterns across many reports
- detect gaps in reproduction information
- route uncertain cases to a human reviewer instead of acting on weak evidence
- automate downstream workflows such as triage dashboards, routing, and monitoring

---

## B. Input

The system input is an unstructured natural-language bug report. It may come from emails, issue trackers, customer support tickets, chat transcripts, or internal QA notes. The input is expected to contain free-form text and may or may not include exact steps to reproduce, error messages, environment details, affected systems, or timing information.

The service must treat the report as the authoritative source of truth for classification and must not assume the report is complete or internally consistent.

### Example messy bug reports

#### Example 1: Clear information
"When I try to log in with a valid SSO account, I get a 500 error after clicking the Sign In button. This started yesterday after the deploy. It only happens in Chrome on Windows 11. The app version is 2.7.4."

Characteristics:
- clear symptom
- likely category: Authentication
- includes environment and timing
- likely reproduction available

#### Example 2: Incomplete information
"The dashboard is broken. It keeps failing when I open it from my phone. Please fix ASAP."

Characteristics:
- lacks app version, browser, exact actions, and failure details
- ambiguous category and severity
- reproduction likely not available or incomplete

#### Example 3: Ambiguous information
"API seems slow and sometimes returns weird stuff. Maybe the DB is lagging? The customer says it happens often, but I cannot tell if it is a login issue or a general service issue."

Characteristics:
- multiple possible causes and domains
- unclear classification
- missing reproduction details
- likely requires human review

#### Example 4: Reproduction steps included
"Steps to reproduce:
1. Log in as an admin
2. Open Settings > Roles
3. Remove a permission from a user
4. Save changes
5. Refresh the page
6. The UI shows the old permission and the API returns 403 on the next request."

Characteristics:
- strong reproduction information
- likely category: Authorization or UI
- clear enough for reproduction_available = true

#### Example 5: Multiple symptoms
"Users report that the checkout page freezes after adding an item to cart, the request times out, and sometimes the order is submitted twice. It seems worse in production after 3pm. It is not happening in staging."

Characteristics:
- multiple symptoms across UI and API
- possible performance and validation concerns
- classification may need to choose primary issue or note multiple symptoms
- reproduction may be partially available but not fully confirmed

---

## C. Structured output

The system produces a structured result representing the classification of a bug report. The output contract is intentionally defined at a high level before implementation. The actual Pydantic schema will be created later, but the semantics are fixed here.

### Required fields

#### category
The primary bug category. This field indicates the dominant issue type reflected in the report.

Allowed initial values:

- Authentication
- Authorization
- API
- UI
- Database
- Performance
- Security
- Validation
- Other

Notes:
- The category should reflect the best interpretation of the bug report, even if the report is ambiguous.
- If none of the defined categories fit well, use Other.
- When multiple categories appear, the system should prefer the most likely root issue or primary symptom.

#### severity
The operational impact or urgency suggested by the report.

Allowed values:

- Critical
- High
- Medium
- Low

Interpretation guidance:
- Critical: severe user impact, outage, security compromise, or critical data loss risk
- High: major user impact or important business workflow interruption
- Medium: noticeable degradation with limited scope or moderate customer impact
- Low: minor issue or low-risk defect

#### priority
The intended triage priority for planning and delivery.

Allowed values:

- P0
- P1
- P2
- P3

Interpretation guidance:
- P0: emergency fix required immediately
- P1: high urgency; should be worked soon
- P2: planned normal priority
- P3: lower urgency or deferred if necessary

#### environment
A description of the environment in which the issue occurs, such as product area, deployment stage, platform, browser, operating system, version, region, or infrastructure context.

Notes:
- This field is intentionally not overly rigid at the specification stage.
- It should capture whatever environment details are present in the report.
- If no environment information is available, the field should still be returned in a meaningful representation, such as a placeholder or a low-detail string rather than invented data.

#### issue
A concise summary of the issue described by the report. This should capture the primary problem in natural, declarative language.

Notes:
- This field should not be a free-form narrative of the whole ticket.
- It should summarize the main bug as the system understands it.
- If the report is ambiguous, the summary should reflect the most likely issue without overstating certainty.

#### reproduction_available
Boolean indicating whether the report contains enough information to understand how the problem can be reproduced.

This field is defined in detail in the next section.

#### confidence
A numeric confidence score representing the classifier's confidence in the structured result.

Requirements:
- Must be between 0.0 and 1.0 inclusive
- Lower values indicate more uncertainty
- Higher values indicate stronger evidence and clearer reports
- Confidence should be treated as one signal, not proof of correctness

#### requires_human_review
Boolean indicating whether the result should be escalated to a human reviewer before acting on the classification.

Notes:
- This is not the same as "the system failed."
- A report may be valid and still require human review because it is ambiguous, incomplete, or high-risk.
- Human review should be triggered when the confidence is low or when key facts are missing.

---

## D. reproduction_available

The field reproduction_available is true when the report contains enough information to understand how the problem can be reproduced.

In practical terms, a report is considered reproduction-capable when it includes enough detail for another engineer or reviewer to reasonably infer the sequence of actions, conditions, and context needed to try the issue again.

### A report should be considered true when it contains enough runtime context such as:

- a clear action or sequence of actions
- affected input or object state
- relevant environment or platform constraints
- when the issue happens and under what conditions
- symptoms that make the failure identifiable

Examples of true cases:

- "Open the account settings page as a user with no permissions, click Save, and the page throws a 403 error."
- "On iPhone Safari 17, visit /checkout, add a product, tap place order, and the spinner never resolves."
- "In staging, log in as Admin, navigate to User Management, edit a role, then refresh and the previous permission reappears."

### A report should be considered false when critical details are missing or the problem cannot be reasonably reproduced from the text alone.

Examples of false cases:

- "The app is broken after the last deploy."
- "Checkout is failing for some users and it is really bad."
- "The dashboard is slow sometimes, not sure what triggers it."
- "Users are seeing weird authentication errors; maybe the login flow is impacted."

### Importance of the field
This field helps with triage quality because reproduction information is often the difference between a deployable bug and a vague ticket. It also supports automation by enabling routing and escalation based on reproducibility.

---

## E. Human-review routing

Human review is a controlled escalation mechanism for reports that should not be trusted automatically.

### Initial review policy
The initial policy should use multiple signals, not confidence alone. The following factors should be considered:

- low confidence score
- missing or weak reproduction information
- ambiguous reporting language
- conflicting symptoms or multiple possible categories
- insufficient environment details for a high-risk issue
- suspicious or contradictory facts

### Example review triggers
A result should be routed for human review when any of the following applies:

- confidence is below a configured threshold
- reproduction_available is false and the issue is not obviously low-risk
- the report is ambiguous enough that more than one likely category is plausible
- required details are missing for a Critical or High severity issue
- the issue appears to involve security, data integrity, or outage conditions and cannot be validated from the report alone

### Important principle
Confidence is a useful signal, but it does not prove correctness. A report can have moderate to high confidence while still being incomplete or misleading. Similarly, a low-confidence report is not automatically useless, but it should be reviewed before acting on it.

### Configuration and evaluation
The exact thresholds for confidence, reproduction availability, and review routing are configurable and must be validated through evaluation. The specification intentionally avoids hardcoding final thresholds because they should be tuned using a representative benchmark dataset and measured outcomes.

---

## F. Failure categories

The system must classify outcomes into a controlled set of failure categories when processing fails or when the output is not trustworthy. This supports observability, retry logic, and stakeholder reporting.

Initial vocabulary:

- INVALID_SCHEMA
- LOW_CONFIDENCE
- AMBIGUOUS_REPORT
- MISSING_INFORMATION
- LLM_TIMEOUT
- RATE_LIMITED
- PROVIDER_ERROR

### When each should be used

#### INVALID_SCHEMA
Used when the model output does not conform to the expected structure or cannot be validated by the downstream schema checker.

#### LOW_CONFIDENCE
Used when the classification has a confidence score or overall decision quality below an acceptable band, even if the output is structurally valid.

#### AMBIGUOUS_REPORT
Used when the input contains conflicting, vague, or mixed signals that prevent a reliable classification.

#### MISSING_INFORMATION
Used when the report is too incomplete to determine the category, seriousness, or reproduction status with acceptable confidence.

#### LLM_TIMEOUT
Used when the model request exceeds the configured timeout window.

#### RATE_LIMITED
Used when the provider rejects a request due to rate limits or quota exhaustion.

#### PROVIDER_ERROR
Used for upstream provider failures not otherwise classified, such as service degradation or invalid provider responses.

These categories are intended to support operational visibility and to isolate the reason the classification failed or was rejected.

---

## G. Evaluation goals

The project should eventually be evaluated against a representative dataset and measured with clear metrics. The evaluation should not be treated as an afterthought; it should define whether the classifier is useful in practice.

### Metrics to measure

#### schema compliance
Percentage of outputs that conform to the defined structured contract.

#### category accuracy
How often the predicted category matches the ground-truth label for the report.

#### severity accuracy
How often severity matches the expected value.

#### priority accuracy
How often priority matches the expected value.

#### reproduction_available accuracy
How often the field matches the expected reproduction status.

#### human-review routing behavior
How often reports that should be reviewed are actually routed to human review, and how often reports that should not be reviewed are incorrectly escalated.

#### failure rate
How often the service fails outright, rejects outputs, times out, or returns fallback/failed classifications.

### Evaluation principle
The project should compare model results against a representative set of labeled bug reports and should track not only accuracy but also failure modes and explainability gaps. The exact thresholds and target numbers will be established later when the dataset and validation pipeline are implemented.

---

## H. Non-goals

The project will not:

- automatically fix bugs in source code
- modify application code or create patches
- replace developers, QA engineers, or support teams
- guarantee certainty when the input is ambiguous
- infer hidden facts not present in the user report
- claim correctness simply because a result is structured or valid
- replace a production incident process or on-call procedure

The system is a triage and classification assistant, not an autonomous debugging or patching platform.

---

## I. Security and privacy considerations

The project must follow basic operational safety requirements from the beginning.

### Required practices

- no API keys or provider credentials in source code
- secrets must be loaded from environment variables or a secure configuration mechanism
- logs must avoid unnecessary sensitive information
- evaluation data must be non-sensitive and should not include production customer data
- complete user inputs should not be logged unless required for debugging and controlled by explicit policy
- failures must be categorized and logged without exposing secrets or sensitive payloads
- the system should minimize leakage of personally identifiable information or confidential application details into traces

### Logging guidance
Logging should include enough information to debug classification failures and routing decisions without recording unrestricted raw content from user reports. Trace records should capture operational metadata, model metadata, validation outcomes, and failure codes while preserving privacy boundaries.

---

## Summary

This project is a structured, safety-oriented bug-classification service for natural-language reports. It is designed to help teams process noisy issue descriptions into consistent, validated classifications while explicitly handling uncertainty, missing reproduction details, and operational failures. The implementation will be added only after this specification is reviewed and approved.
