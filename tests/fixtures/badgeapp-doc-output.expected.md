# BadgeApp Security Assurance Case

This document presents the security assurance case for the BadgeApp system,
arguing that it is adequately secure against moderate threats.

## Packages

<!-- verocase sacm/mermaid * -->
### Package Security
```mermaid
---
config:
  theme: neutral
  flowchart:
    curve: linear
    htmlLabels: true
    rankSpacing: 60
    nodeSpacing: 45
    padding: 15
---
flowchart BT
    classDef invisible opacity:0
    classDef sacmDot fill:#000,stroke:#000
    classDef connector fill:none,stroke:#cccccc,stroke-width:1px;
    classDef abstractClaim stroke-width:2px,stroke-dasharray: 5 5;
    Security_L1["<b>Security</b><br>The system is adequately secure against moderate threats"]
    Processes_L2[/"<b>Processes</b><br>Security is argued by examining lifecycle processes"/]
    Technical_L3["<b>Technical</b><br>Technical lifecycle processes implement security"]
    NonTechnical_L10[["<b>NonTechnical</b><br>Non-technical lifecycle processes implement security"]]
    Controls_L11[["<b>Controls</b><br>Certifications &amp; controls provide confidence in operating results"]]
    Requirements_L4[["<b>Requirements</b>"]]
    Design_L5[["<b>Design</b><br>The security design is documented and reviewed"]]
    Implementation_L6[["<b>Implementation</b><br>The implementation process maintains security"]]
    Verification_L7[["<b>Verification</b><br>Integration &amp; verification confirm security"]]
    Deployment_L8[["<b>Deployment</b><br>Deployment maintains security"]]
    Maintenance_L9[["<b>Maintenance</b><br>The maintenance process maintains security"]]
    Dot1((" ")):::sacmDot
    Dot2((" ")):::sacmDot
    click Security_L1 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/badgeapp-doc-output.expected.md#claim-security"
    click Processes_L2 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/badgeapp-doc-output.expected.md#strategy-processes"
    click Technical_L3 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/badgeapp-doc-output.expected.md#claim-technical"
    click NonTechnical_L10 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/badgeapp-doc-output.expected.md#package-nontechnical"
    click Controls_L11 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/badgeapp-doc-output.expected.md#package-controls"
    click Requirements_L4 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/badgeapp-doc-output.expected.md#package-requirements"
    click Design_L5 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/badgeapp-doc-output.expected.md#package-design"
    click Implementation_L6 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/badgeapp-doc-output.expected.md#package-implementation"
    click Verification_L7 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/badgeapp-doc-output.expected.md#package-verification"
    click Deployment_L8 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/badgeapp-doc-output.expected.md#package-deployment"
    click Maintenance_L9 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/badgeapp-doc-output.expected.md#package-maintenance"

    BottomPadding[ ]:::invisible ~~~ Requirements_L4
    Requirements_L4 --- Dot1
    Design_L5 --- Dot1
    Implementation_L6 --- Dot1
    Verification_L7 --- Dot1
    Deployment_L8 --- Dot1
    Maintenance_L9 --- Dot1
    Dot1 --> Technical_L3
    Technical_L3 --- Dot2
    NonTechnical_L10 --- Dot2
    Controls_L11 --- Dot2
    Processes_L2 --- Dot2
    Dot2 --> Security_L1
```

### Package Requirements
```mermaid
---
config:
  theme: neutral
  flowchart:
    curve: linear
    htmlLabels: true
    rankSpacing: 60
    nodeSpacing: 45
    padding: 15
---
flowchart BT
    classDef invisible opacity:0
    classDef sacmDot fill:#000,stroke:#000
    classDef connector fill:none,stroke:#cccccc,stroke-width:1px;
    classDef abstractClaim stroke-width:2px,stroke-dasharray: 5 5;
    Requirements_L13["<b>Requirements</b><br>Security requirements are identified and met"]
    ReqSpec_L14[("<b>ReqSpec</b>&nbsp;↗<br>Requirements specification")]
    TestCoverage_L15[("<b>TestCoverage</b>&nbsp;↗<br>Test coverage report")]
    ReqScope_L16[("<b>ReqScope</b>&nbsp;↗<br>Applies to all user-facing features")]
    Dot1((" ")):::sacmDot
    click Requirements_L13 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/badgeapp-doc-output.expected.md#claim-requirements"
    click ReqSpec_L14 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/badgeapp-doc-output.expected.md#evidence-reqspec"
    click TestCoverage_L15 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/badgeapp-doc-output.expected.md#evidence-testcoverage"
    click ReqScope_L16 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/badgeapp-doc-output.expected.md#context-reqscope"

    BottomPadding[ ]:::invisible ~~~ ReqSpec_L14
    ReqSpec_L14 --- Dot1
    TestCoverage_L15 --- Dot1
    Dot1 --> Requirements_L13
    ReqScope_L16 --o Requirements_L13
```

### Package Design
```mermaid
---
config:
  theme: neutral
  flowchart:
    curve: linear
    htmlLabels: true
    rankSpacing: 60
    nodeSpacing: 45
    padding: 15
---
flowchart BT
    classDef invisible opacity:0
    classDef sacmDot fill:#000,stroke:#000
    classDef connector fill:none,stroke:#cccccc,stroke-width:1px;
    classDef abstractClaim stroke-width:2px,stroke-dasharray: 5 5;
    Design_L18["<b>Design</b><br>The security design is documented and reviewed"]
    DesignDoc_L19[("<b>DesignDoc</b>&nbsp;↗<br>Security architecture document")]
    ThreatModel_L20[("<b>ThreatModel</b>&nbsp;↗<br>Threat model")]
    Dot1((" ")):::sacmDot
    click Design_L18 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/badgeapp-doc-output.expected.md#claim-design"
    click DesignDoc_L19 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/badgeapp-doc-output.expected.md#evidence-designdoc"
    click ThreatModel_L20 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/badgeapp-doc-output.expected.md#evidence-threatmodel"

    BottomPadding[ ]:::invisible ~~~ DesignDoc_L19
    DesignDoc_L19 --- Dot1
    ThreatModel_L20 --- Dot1
    Dot1 --> Design_L18
```
<!-- end verocase -->

## Context Details

Additional context and evidence packages supporting the argument.

<!-- verocase element Security -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="claim-security"></a>
### Claim Security: The system is adequately secure against moderate threats

Referenced by: **[Package Security](#package-security)**

Supported by: **[Strategy Processes](#strategy-processes)**
<!-- end verocase -->

This is the top-level claim for the entire assurance case.

<!-- verocase element Requirements -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="claim-requirements"></a>
### Claim Requirements: Security requirements are identified and met

Referenced by: **[Package Requirements](#package-requirements)**, [Package Security](#package-security)

Supported by: **[Evidence ReqSpec](#evidence-reqspec)**, [Evidence TestCoverage](#evidence-testcoverage), [Context ReqScope](#context-reqscope)

Supports: [Claim Technical](#claim-technical)
<!-- end verocase -->

The security requirements are documented and verified against the implementation.

<!-- verocase element Design -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="claim-design"></a>
### Claim Design: The security design is documented and reviewed

Referenced by: **[Package Design](#package-design)**, [Package Security](#package-security)

Supported by: **[Evidence DesignDoc](#evidence-designdoc)**, [Evidence ThreatModel](#evidence-threatmodel)

Supports: [Claim Technical](#claim-technical)
<!-- end verocase -->

The system design incorporates security from the ground up.

<!-- verocase element ReqSpec -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="evidence-reqspec"></a>
### Evidence ReqSpec: Requirements specification

Referenced by: **[Package Requirements](#package-requirements)**

Supports: **[Claim Requirements](#claim-requirements)**

External Reference: [docs/requirements.md](https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/docs/requirements.md)
<!-- end verocase -->

See the full requirements document for details.

<!-- verocase element TestCoverage -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="evidence-testcoverage"></a>
### Evidence TestCoverage: Test coverage report

Referenced by: **[Package Requirements](#package-requirements)**

Supports: **[Claim Requirements](#claim-requirements)**

External Reference: [reports/coverage.html](https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/reports/coverage.html)
<!-- end verocase -->

All security tests pass with full coverage of requirements.

<!-- verocase element DesignDoc -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="evidence-designdoc"></a>
### Evidence DesignDoc: Security architecture document

Referenced by: **[Package Design](#package-design)**

Supports: **[Claim Design](#claim-design)**

External Reference: [docs/security-arch.pdf](https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/docs/security-arch.pdf)
<!-- end verocase -->

The architecture has been reviewed by the security team.

<!-- verocase element ThreatModel -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="evidence-threatmodel"></a>
### Evidence ThreatModel: Threat model

Referenced by: **[Package Design](#package-design)**

Supports: **[Claim Design](#claim-design)**

External Reference: [docs/threat-model.md](https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/docs/threat-model.md)
<!-- end verocase -->

Threats are systematically identified and mitigated.

<!-- verocase element ReqScope -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="context-reqscope"></a>
### Context ReqScope: Applies to all user-facing features

Referenced by: **[Package Requirements](#package-requirements)**

Supports: **[Claim Requirements](#claim-requirements)**
<!-- end verocase -->

Defines the scope of the requirements coverage.
