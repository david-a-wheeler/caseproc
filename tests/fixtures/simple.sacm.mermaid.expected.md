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
    click C1 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/simple.sacm.mermaid.expected.md#claim-c1"
    click AR1 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/simple.sacm.mermaid.expected.md#strategy-ar1"
    click A1 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/simple.sacm.mermaid.expected.md#assumption-a1"
    click X1 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/simple.sacm.mermaid.expected.md#context-x1"
    click C2 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/simple.sacm.mermaid.expected.md#claim-c2"
    click C3 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/simple.sacm.mermaid.expected.md#claim-c3"
    click E1 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/simple.sacm.mermaid.expected.md#evidence-e1"

    BottomPadding[ ]:::invisible ~~~ AR1
    BottomPadding ~~~ A1
    BottomPadding ~~~ X1
    BottomPadding ~~~ C3
    BottomPadding ~~~ E1
    E1 --> C2
    C2 --- Dot1
    C3 --- Dot1
    AR1 --- Dot1
    A1 --- Dot1
    Dot1 --> C1
    X1 --o C1
```
