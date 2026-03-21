# Demo Website Security Assurance Case

This document presents the security assurance case for a public-facing web
application, arguing that it is adequately secure against moderate threats.
The case is structured as four sub-arguments—access control, data
protection, deployment, and monitoring—each supporting the overarching
security claim.

It's really a demo of some of our capabilities, including four different
GSN Strategy renderings: one with no Context or Justification children
(SArg), one with a single Context (SAccess), one with a Context and a
Justification (SData), and one with a Context, a Justification, and a
second Context (SMonitor).

## SACM Diagrams

<!-- verocase sacm/mermaid * -->
stale content
<!-- end verocase -->

## GSN Diagrams

<!-- verocase gsn/mermaid * -->
stale content
<!-- end verocase -->

## CAE Diagrams

<!-- verocase cae/mermaid * -->
stale content
<!-- end verocase -->

## LTAC Notation

<!-- verocase ltac/markdown * -->
stale content
<!-- end verocase -->

## Element Details

<!-- verocase element Security -->
<!-- end verocase -->

The website must withstand opportunistic attacks and targeted attacks up to
the level described by the OWASP Top Ten threat model. This is the
top-level claim the entire assurance case supports.

<!-- verocase element XScope -->
<!-- end verocase -->

OWASP Top Ten is a widely recognised baseline threat model for public-facing
web applications, updated annually to reflect current attacker techniques.
It was agreed with the customer as the applicable scope for this engagement.

<!-- verocase element SArg -->
<!-- end verocase -->

The argument is decomposed into four parallel sub-arguments. Access control,
data protection, deployment configuration, and security monitoring are argued
independently; each sub-argument supports the top-level security claim.
SArg demonstrates a Strategy with no Context or Justification children.

<!-- verocase element Access -->
<!-- end verocase -->

This claim covers the mechanisms that prevent unauthorised users from
reading, modifying, or destroying resources. It encompasses authentication,
authorisation, and protection against client-side injection attacks.

<!-- verocase element AAdmin -->
<!-- end verocase -->

Administrators are responsible for creating and revoking accounts, assigning
roles, and following the access management policy. Deliberate misuse by
administrators is outside the threat model for this case.

<!-- verocase element SAccess -->
<!-- end verocase -->

Access control is argued by examining the authentication mechanism,
role-based authorisation configuration, and mitigations for the two most
prevalent web injection attack classes: XSS and SQL injection.
SAccess demonstrates a Strategy with a single Context child (XAuthStd),
which GSN renders beside the Strategy rather than below it.

<!-- verocase element XAuthStd -->
<!-- end verocase -->

NIST SP 800-63B Authenticator Assurance Level 2 is the baseline required
for applications handling personal data. The standard mandates a
multi-factor authentication mechanism resistant to phishing and replay
attacks, and serves as the normative reference for all authentication
claims in this sub-argument.

<!-- verocase element AuthN -->
<!-- end verocase -->

All accounts require a password and a time-based one-time password (TOTP)
token before a session is established. Failed attempts trigger a progressive
delay and are recorded in the audit log.

<!-- verocase element EvLogin -->
<!-- end verocase -->

Login audit logs for the preceding 90 days were reviewed. No sessions were
established without a successful MFA challenge, and no accounts showed
anomalous access patterns.

<!-- verocase element JMechanism -->
<!-- end verocase -->

Password-plus-TOTP corresponds to NIST SP 800-63B AAL2, the recommended
assurance level for applications handling personal data. It defends against
both password-stuffing attacks and phished credentials.

<!-- verocase element XLogPolicy -->
<!-- end verocase -->

The log retention policy requires all authentication events to be retained
for a minimum of 90 days, satisfying the audit window needed to detect
slow-burn credential-abuse campaigns.

<!-- verocase element AuthZ -->
<!-- end verocase -->

Permissions are assigned by role; no user is granted capabilities beyond
those their role requires. Role assignments are reviewed quarterly by the
access control team and approved by the relevant department head.

<!-- verocase element EvRBAC -->
<!-- end verocase -->

An independent configuration review compared the RBAC policy document
against the live permission tables. No over-privileged accounts or role
violations were found.

<!-- verocase element AuthZAdmin -->
<!-- end verocase -->

Elevated administrative actions require the operator to re-authenticate into
a separate privileged session with a short timeout. This architectural
control is assumed to be correctly enforced by the framework.

<!-- verocase element XSSFree -->
<!-- end verocase -->

Cross-site scripting is mitigated through a Content Security Policy that
blocks inline scripts and restricts script sources, combined with
context-aware output encoding on all dynamic content.

<!-- verocase element EvCSP -->
<!-- end verocase -->

An automated CSP scanner confirmed that policy headers are present on all
public endpoints and that the policy is sufficiently restrictive to block
known inline-script injection patterns.

<!-- verocase element R1 -->
<!-- end verocase -->

The penetration test found XSS vulnerabilities on several endpoints that
lack consistent output encoding, indicating that the mitigations are not
uniformly applied. This is cited as a counter-argument to XSSFree.

<!-- verocase element SqlFree -->
<!-- end verocase -->

SQL injection was intended to be prevented through an ORM layer and
mandatory use of parameterised queries. However, a penetration test
revealed a legacy code path that bypasses the ORM, making this claim
defeated: remediation is required before the case can be reasserted.

<!-- verocase element EvPenTest -->
<!-- end verocase -->

A targeted penetration test was conducted against the application by an
external security firm. The report identified an actively exploitable SQL
injection vulnerability in the search endpoint (severity: Critical) and
flagged multiple endpoints with inconsistent XSS output encoding.

<!-- verocase element DBVuln -->
<!-- end verocase -->

The search endpoint constructs a query by string concatenation when the
ORM cache misses, admitting direct SQL injection. This vulnerability
defeats the SqlFree claim and must be remediated before the assurance
case can be reasserted.

<!-- verocase element Data -->
<!-- end verocase -->

Personal data collected by the application must be protected against
disclosure and tampering both in transit (over the network) and at rest
(in the database and backups). Handling must comply with applicable
privacy regulations.

<!-- verocase element XRegulation -->
<!-- end verocase -->

GDPR and applicable state privacy laws impose obligations on data
collection, processing, retention, and breach notification. The privacy
policy covering these obligations has been reviewed by legal counsel.

<!-- verocase element AEncrypt -->
<!-- end verocase -->

The correctness of the TLS 1.3 protocol itself is taken as axiomatic,
established by the IETF specification (RFC 8446) and extensive
cryptographic review. This case argues only that TLS 1.3 is correctly
deployed, not that the protocol is sound.

<!-- verocase element SData -->
<!-- end verocase -->

Data protection is argued across four concerns: encryption of data in
transit, encryption of data at rest, minimisation of data collected and
retained, and audit logging of access to sensitive records.
SData demonstrates a Strategy with a Context child (XDataScope) and a
Justification child (JDataArch), which GSN renders flanking the Strategy.

<!-- verocase element XDataScope -->
<!-- end verocase -->

GDPR Article 32 requires controllers to implement appropriate technical
measures to ensure a level of security appropriate to the risk, including
encryption and ongoing confidentiality assurance. Applicable state privacy
laws impose equivalent or stricter obligations. These instruments define
the normative scope for all data protection claims in this sub-argument.

<!-- verocase element JDataArch -->
<!-- end verocase -->

Separating encryption, data minimisation, and audit logging into
independent sub-arguments follows the EDPB's layered security guidance
and makes each concern independently verifiable. This decomposition also
simplifies gap analysis against GDPR Article 32 compliance checklists.

<!-- verocase element Encrypt -->
<!-- end verocase -->

All external connections use TLS 1.3 with HSTS enforced. Database
volumes are encrypted with AES-256-GCM; encryption keys are stored in a
hardware security module and rotated annually.

<!-- verocase element EvTLS -->
<!-- end verocase -->

An SSL Labs scan awarded the application an A+ rating, confirming correct
cipher-suite selection, HSTS preloading, and OCSP stapling on all
public-facing endpoints.

<!-- verocase element EvDB -->
<!-- end verocase -->

An independent database audit confirmed that encryption-at-rest is enabled
for all volumes containing personal data and that key management procedures
comply with the organisation's cryptographic standards policy.

<!-- verocase element Minimise -->
<!-- end verocase -->

The application collects only fields required for the stated service
purpose. Retention schedules are enforced by an automated purge job that
runs nightly and is monitored for failures.

<!-- verocase element DataMap -->
<!-- end verocase -->

The data flow diagram captures all personal data inputs, stores, processing
steps, and outputs. It has been drafted but formal sign-off from the data
protection officer is pending; this claim is therefore marked as needing
further support.

<!-- verocase element JRetention -->
<!-- end verocase -->

Collecting and retaining only the minimum necessary data reduces the impact
of a breach (less data exposed), simplifies compliance with GDPR Article
5(1)(e) (storage limitation), and lowers the cost of subject-access-request
responses.

<!-- verocase element AuditAccess -->
<!-- end verocase -->

Every read or write to a sensitive data record is appended to an
append-only audit log. The security team reviews the log for anomalous
patterns; the review cadence and escalation procedures are defined in the
forthcoming access monitoring policy, which has not yet been finalised.

<!-- verocase element MetaClaim -->
<!-- end verocase -->

The data protection sub-argument was structured against the GDPR compliance
checklist. Each checklist item maps to at least one claim or evidence
element in the case, ensuring no data protection requirement is
inadvertently omitted.

<!-- verocase element Deployment -->
<!-- end verocase -->

The server configuration is derived from the CIS Benchmark hardening
profile for the operating system and is enforced via infrastructure-as-code.
Drift from the baseline triggers an automated alert.

<!-- verocase element EvHarden -->
<!-- end verocase -->

The server hardening checklist was completed and signed off by the
infrastructure security team. The review covered OS-level patches, removal
of unnecessary services, firewall ingress rules, and file-permission
hardening.

<!-- verocase element XProd -->
<!-- end verocase -->

The production environment is configured to reject plain HTTP connections.
HTTP requests are redirected to HTTPS at the load balancer before reaching
any application code, preventing accidental cleartext transmission.

<!-- verocase element Monitoring -->
<!-- end verocase -->

Security event detection and response is essential for identifying active
attacks and limiting their impact. This claim covers the operational
capability to detect, triage, and respond to security events in time to
prevent material harm.

<!-- verocase element SMonitor -->
<!-- end verocase -->

Detection capability is argued by examining three orthogonal concerns:
the breadth of SIEM event-source coverage, the SOC staffing model that
ensures human review is always available, and the contractual response-time
obligations that bound acceptable latency.
SMonitor demonstrates a Strategy with three Context/Justification children.
The first two (XSIEMScope and JSOCModel) are rendered beside the Strategy
in GSN; the third (XSLA) remains below as a regular in-context-of child.

<!-- verocase element XSIEMScope -->
<!-- end verocase -->

The SIEM is configured to ingest logs from all application servers, load
balancers, database engines, and network perimeter devices. Full coverage
is a prerequisite for the alerting-coverage claim; gaps in ingestion would
create blind spots that make AlertCoverage unverifiable.

<!-- verocase element JSOCModel -->
<!-- end verocase -->

The follow-the-sun model staffs the SOC across three regional teams in
overlapping shifts, eliminating the after-hours coverage gaps common in
single-region operations. This staffing structure is the organisational
justification for asserting that human review is continuously available.

<!-- verocase element XSLA -->
<!-- end verocase -->

The service-level agreement with the customer specifies a 15-minute
acknowledgment target for P1 (critical) security alerts. This contractual
obligation defines the quantitative threshold against which the
ResponseTime claim is measured.

<!-- verocase element AlertCoverage -->
<!-- end verocase -->

The SIEM rule set is mapped against the OWASP Top Ten. Each attack
category must have at least one detection rule with a documented test
case confirming it fires on a representative attack sample.

<!-- verocase element EvAlertCoverage -->
<!-- end verocase -->

An annual SIEM rule audit reviewed all active detection rules against the
current OWASP Top Ten list. Every attack category had at least one
matching rule, and each rule had a passing test case in the rule-testing
framework.

<!-- verocase element ResponseTime -->
<!-- end verocase -->

Alert acknowledgment time is measured from the moment a P1 alert fires
in the SIEM to the moment a SOC analyst marks it as under investigation.
The claim requires this latency to remain within the SLA threshold.

<!-- verocase element EvResponseTime -->
<!-- end verocase -->

Monthly SOC performance reports for the preceding 12 months were reviewed.
Across 847 P1 alerts raised during the period, 99.2% were acknowledged
within 15 minutes. The eight exceptions were all caused by a single
infrastructure outage and were covered by the SLA's force-majeure clause.
