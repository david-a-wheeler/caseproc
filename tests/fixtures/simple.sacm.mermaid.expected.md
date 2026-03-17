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
    click C1_L1 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/simple.sacm.mermaid.expected.md#claim-c1"
    click AR1_L2 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/simple.sacm.mermaid.expected.md#strategy-ar1"
    click A1_L7 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/simple.sacm.mermaid.expected.md#assumption-a1"
    click X1_L8 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/simple.sacm.mermaid.expected.md#context-x1"
    click C2_L3 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/simple.sacm.mermaid.expected.md#claim-c2"
    click C3_L5 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/simple.sacm.mermaid.expected.md#claim-c3"
    click E1_L4 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/simple.sacm.mermaid.expected.md#evidence-e1"

    BottomPadding[ ]:::invisible ~~~ E1_L4
    E1_L4 --> C2_L3
    C2_L3 --- Dot1
    C3_L5 --- Dot1
    AR1_L2 --- Dot1
    A1_L7 --- Dot1
    Dot1 --> C1_L1
    X1_L8 --o C1_L1
```
