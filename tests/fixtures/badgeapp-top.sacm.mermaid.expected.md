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
    Top_L1["<b>Top</b><br>The system is adequately secure against moderate threats"]
    Processes_L2[/"<b>Processes</b><br>Security is argued by examining lifecycle processes"/]
    Technical_L3["<b>Technical</b><br>Technical lifecycle processes implement security"]
    NonTechnical_L10[["<b>NonTechnical</b><br>Non-technical lifecycle processes implement security"]]
    Controls_L11[["<b>Controls</b><br>Certifications &amp; controls provide confidence in operating results"]]
    Requirements_L4[["<b>Requirements</b><br>Security requirements are identified and met by the implementation"]]
    Design_L5[["<b>Design</b><br>The design has security built in"]]
    Implementation_L6[["<b>Implementation</b><br>The implementation process maintains security"]]
    Verification_L7[["<b>Verification</b><br>Integration &amp; verification confirm security"]]
    Deployment_L8[["<b>Deployment</b><br>Deployment maintains security"]]
    Maintenance_L9[["<b>Maintenance</b><br>The maintenance process maintains security"]]
    Dot1((" ")):::sacmDot
    Dot2((" ")):::sacmDot
    click Top_L1 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/badgeapp-top.sacm.mermaid.expected.md#claim-top"
    click Processes_L2 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/badgeapp-top.sacm.mermaid.expected.md#strategy-processes"
    click Technical_L3 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/badgeapp-top.sacm.mermaid.expected.md#claim-technical"
    click NonTechnical_L10 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/badgeapp-top.sacm.mermaid.expected.md#package-nontechnical"
    click Controls_L11 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/badgeapp-top.sacm.mermaid.expected.md#package-controls"
    click Requirements_L4 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/badgeapp-top.sacm.mermaid.expected.md#package-requirements"
    click Design_L5 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/badgeapp-top.sacm.mermaid.expected.md#package-design"
    click Implementation_L6 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/badgeapp-top.sacm.mermaid.expected.md#package-implementation"
    click Verification_L7 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/badgeapp-top.sacm.mermaid.expected.md#package-verification"
    click Deployment_L8 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/badgeapp-top.sacm.mermaid.expected.md#package-deployment"
    click Maintenance_L9 "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/badgeapp-top.sacm.mermaid.expected.md#package-maintenance"

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
    Dot2 --> Top_L1
```
