# BadgeApp Security Assurance Case

This document presents the security assurance case for the BadgeApp system,
arguing that it is adequately secure against moderate threats.

## Packages

<!-- ltac sacm/mermaid * -->
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
    Security["<b>Security</b><br>The system is adequately secure against moderate threats"]
    Processes[/"<b>Processes</b><br>Security is argued by examining lifecycle processes"/]
    Technical["<b>Technical</b><br>Technical lifecycle processes implement security"]
    NonTechnical[["<b>NonTechnical</b><br>Non-technical lifecycle processes implement security"]]
    Controls[["<b>Controls</b><br>Certifications &amp; controls provide confidence in operating results"]]
    Requirements[["<b>Requirements</b><br>Security requirements are identified and met by the implementation"]]
    Design[["<b>Design</b><br>The design has security built in"]]
    Implementation[["<b>Implementation</b><br>The implementation process maintains security"]]
    Verification[["<b>Verification</b><br>Integration &amp; verification confirm security"]]
    Deployment[["<b>Deployment</b><br>Deployment maintains security"]]
    Maintenance[["<b>Maintenance</b><br>The maintenance process maintains security"]]
    Dot1((" ")):::sacmDot
    Dot2((" ")):::sacmDot

    BottomPadding[ ]:::invisible ~~~ Requirements
    Requirements --- Dot1
    Design --- Dot1
    Implementation --- Dot1
    Verification --- Dot1
    Deployment --- Dot1
    Maintenance --- Dot1
    Dot1 --> Technical
    Technical --- Dot2
    NonTechnical --- Dot2
    Controls --- Dot2
    Processes --- Dot2
    Dot2 --> Security
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
    Requirements["<b>Requirements</b><br>Security requirements are identified and met"]
    ReqSpec[("<b>ReqSpec</b>&nbsp;↗<br>Requirements specification")]
    TestCoverage[("<b>TestCoverage</b>&nbsp;↗<br>Test coverage report")]
    ReqScope[("<b>ReqScope</b>&nbsp;↗<br>Applies to all user-facing features")]
    Dot1((" ")):::sacmDot
    click ReqSpec "docs/requirements.md"
    click TestCoverage "reports/coverage.html"

    BottomPadding[ ]:::invisible ~~~ ReqSpec
    ReqSpec --- Dot1
    TestCoverage --- Dot1
    Dot1 --> Requirements
    ReqScope --o Requirements
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
    Design["<b>Design</b><br>The security design is documented and reviewed"]
    DesignDoc[("<b>DesignDoc</b>&nbsp;↗<br>Security architecture document")]
    ThreatModel[("<b>ThreatModel</b>&nbsp;↗<br>Threat model")]
    Dot1((" ")):::sacmDot
    click DesignDoc "docs/security-arch.pdf"
    click ThreatModel "docs/threat-model.md"

    BottomPadding[ ]:::invisible ~~~ DesignDoc
    DesignDoc --- Dot1
    ThreatModel --- Dot1
    Dot1 --> Design
```
<!-- end ltac -->

## Context Details

Additional context and evidence packages supporting the argument.

### Claim Security: The system is adequately secure against moderate threats

<!-- ltac references -->
References: [Package Security](#package-security)
<!-- end ltac -->

This is the top-level claim for the entire assurance case.

### Claim Requirements: Security requirements are identified and met

<!-- ltac references -->
References: [Package Security](#package-security)
<!-- end ltac -->

The security requirements are documented and verified against the implementation.

### Claim Design: The security design is documented and reviewed

<!-- ltac references -->
References: [Package Security](#package-security)
<!-- end ltac -->

The system design incorporates security from the ground up.

### Evidence ReqSpec: Requirements specification

<!-- ltac references -->
References: [Package Requirements](#package-requirements)
<!-- end ltac -->

See the full requirements document for details.

### Evidence TestCoverage: Test coverage report

<!-- ltac references -->
References: [Package Requirements](#package-requirements)
<!-- end ltac -->

All security tests pass with full coverage of requirements.

### Evidence DesignDoc: Security architecture document

<!-- ltac references -->
References: [Package Design](#package-design)
<!-- end ltac -->

The architecture has been reviewed by the security team.

### Evidence ThreatModel: Threat model

<!-- ltac references -->
References: [Package Design](#package-design)
<!-- end ltac -->

Threats are systematically identified and mitigated.

### Context ReqScope: Applies to all user-facing features

<!-- ltac references -->
References: [Package Requirements](#package-requirements)
<!-- end ltac -->

Defines the scope of the requirements coverage.
