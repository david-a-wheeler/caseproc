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
flowchart TD
    classDef invisible opacity:0
    classDef gsnUndev stroke-width:2px,stroke-dasharray: 5 5;
    classDef connector fill:none,stroke:#cccccc,stroke-width:1px;
    C1["<b>C1</b><br>The software is acceptably safe"]
    AR1[/"<b>AR1</b><br>Argue safety by hazard category"/]
    A1("<b>A1</b>&nbsp;Ⓐ<br>Threat model is current")
    X1(["<b>X1</b><br>Scope is release v1.0"])
    C2["<b>C2</b><br>All hazards have been identified"]
    C3["<b>C3</b><br>All hazards have been mitigated"]
    E1(("<b>E1</b><br>Hazard analysis"))
    click C1 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/simple.gsn.mermaid.expected.md#claim-c1"
    click AR1 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/simple.gsn.mermaid.expected.md#strategy-ar1"
    click A1 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/simple.gsn.mermaid.expected.md#assumption-a1"
    click X1 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/release-notes.md"
    click C2 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/simple.gsn.mermaid.expected.md#claim-c2"
    click C3 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/simple.gsn.mermaid.expected.md#claim-c3"
    click E1 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/hara.pdf"

    C1 --> AR1
    AR1 --> C2
    C2 --> E1
    AR1 --> C3
    C3 --> E1
    C1 --o A1
    C1 --o X1
    E1 ~~~ BottomPadding[ ]:::invisible
    A1 ~~~ BottomPadding
    X1 ~~~ BottomPadding
```
