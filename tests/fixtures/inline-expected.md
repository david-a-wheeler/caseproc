# Package C1

## Claim C1: The software is acceptably safe

<!-- ltac statement C1 -->
Statement: The software is acceptably safe
<!-- end ltac -->

<!-- ltac references C1 -->
References: [Package C1](#package-c1)
<!-- end ltac -->

<!-- ltac sacm/mermaid C1 -->
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
    C1["<b>C1</b><br>The software is acceptably safe"]
    AR1[/"<b>AR1</b><br>Argue safety by hazard category"/]
    A1["<b>A1</b><br>Threat model is current<br>ASSUMED"]
    X1[("<b>X1</b>&nbsp;↗<br>Scope is release v1.0")]
    C2["<b>C2</b><br>All hazards have been identified"]
    C3["<b>C3</b><br>All hazards have been mitigated"]
    E1[("<b>E1</b>&nbsp;↗<br>Hazard analysis")]
    Dot1((" ")):::sacmDot
    click X1 "release-notes.md"
    click E1 "hara.pdf"

    BottomPadding[ ]:::invisible ~~~ E1
    E1 --> C2
    C2 --- Dot1
    C3 --- Dot1
    AR1 --- Dot1
    A1 --- Dot1
    Dot1 --> C1
    X1 --o C1
```
<!-- end ltac -->
