<!-- verocase package C1 -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="package-c1"></a>
### Package C1: The software is acceptably safe

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
    C1_L1["<b>C1</b><br>The software is acceptably safe"]
    AR1_L2[/"<b>AR1</b><br>Argue safety by hazard category"/]
    A1_L7["<b>A1</b><br>Threat model is current<br>ASSUMED"]
    X1_L8[("<b>X1</b>&nbsp;↗<br>Scope is release v1.0")]
    C2_L3["<b>C2</b><br>All hazards have been identified"]
    C3_L5["<b>C3</b><br>All hazards have been mitigated"]
    E1_L4[("<b>E1</b>&nbsp;↗<br>Hazard analysis")]
    Dot1((" ")):::sacmDot
    click C1_L1 "#claim-c1"
    click AR1_L2 "#strategy-ar1"
    click A1_L7 "#assumption-a1"
    click X1_L8 "#context-x1"
    click C2_L3 "#claim-c2"
    click C3_L5 "#claim-c3"
    click E1_L4 "#evidence-e1"

    BottomPadding[ ]:::invisible ~~~ E1_L4
    E1_L4 --> C2_L3
    C2_L3 --- Dot1
    C3_L5 --- Dot1
    AR1_L2 --- Dot1
    A1_L7 --- Dot1
    Dot1 --> C1_L1
    X1_L8 --o C1_L1
```

Defines: **[Claim C1](#claim-c1)**, [Context X1](#context-x1), [Assumption A1](#assumption-a1), [Strategy AR1](#strategy-ar1), [Claim C3](#claim-c3), [Claim C2](#claim-c2), [Evidence E1](#evidence-e1)
<!-- end verocase -->

<!-- verocase element C1 -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="claim-c1"></a>
### Claim C1: The software is acceptably safe

Referenced by: **[Package C1](#package-c1)**

Supported by: **[Strategy AR1](#strategy-ar1)**, [Assumption A1](#assumption-a1), [Context X1](#context-x1)
<!-- end verocase -->

<!-- verocase statement C1 -->
Statement: The software is acceptably safe
<!-- end verocase -->

<!-- verocase sacm/mermaid C1 -->
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
    C1_L1["<b>C1</b><br>The software is acceptably safe"]
    AR1_L2[/"<b>AR1</b><br>Argue safety by hazard category"/]
    A1_L7["<b>A1</b><br>Threat model is current<br>ASSUMED"]
    X1_L8[("<b>X1</b>&nbsp;↗<br>Scope is release v1.0")]
    C2_L3["<b>C2</b><br>All hazards have been identified"]
    C3_L5["<b>C3</b><br>All hazards have been mitigated"]
    E1_L4[("<b>E1</b>&nbsp;↗<br>Hazard analysis")]
    Dot1((" ")):::sacmDot
    click C1_L1 "#claim-c1"
    click AR1_L2 "#strategy-ar1"
    click A1_L7 "#assumption-a1"
    click X1_L8 "#context-x1"
    click C2_L3 "#claim-c2"
    click C3_L5 "#claim-c3"
    click E1_L4 "#evidence-e1"

    BottomPadding[ ]:::invisible ~~~ E1_L4
    E1_L4 --> C2_L3
    C2_L3 --- Dot1
    C3_L5 --- Dot1
    AR1_L2 --- Dot1
    A1_L7 --- Dot1
    Dot1 --> C1_L1
    X1_L8 --o C1_L1
```
<!-- end verocase -->
