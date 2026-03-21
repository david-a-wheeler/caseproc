# Website Security Assurance Case

This document presents the security assurance case for a public-facing web
application, arguing that it is adequately secure against moderate threats.
The case is structured as three sub-arguments—access control, data
protection, and deployment—each supporting the overarching security claim.

## SACM Diagrams

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
    Security["<b>Security</b><br>The website is adequately secure against moderate threats"]
    XScope[("<b>XScope</b>&nbsp;↗<br>OWASP Top Ten threat model defines the threat scope")]
    SArg[/"<b>SArg</b><br>Security is argued by examining access control, data protection, and deployment"/]
    Access[["<b>Access</b>"]]
    Data[["<b>Data</b>"]]
    Deployment["<b>Deployment</b><br>Deployment configuration follows security hardening guidelines"]
    EvHarden[("<b>EvHarden</b>&nbsp;↗<br>Server hardening checklist completed and signed off")]
    XProd[("<b>XProd</b>&nbsp;↗<br>Production environment enforces HTTPS-only connections")]
    Dot1((" ")):::sacmDot
    click Security "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-security"
    click XScope "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#context-xscope"
    click SArg "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#strategy-sarg"
    click Access "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#package-access"
    click Data "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#package-data"
    click Deployment "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-deployment"
    click EvHarden "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#evidence-evharden"
    click XProd "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#context-xprod"

    BottomPadding[ ]:::invisible ~~~ XScope
    BottomPadding ~~~ SArg
    BottomPadding ~~~ Access
    BottomPadding ~~~ Data
    BottomPadding ~~~ EvHarden
    BottomPadding ~~~ XProd
    EvHarden --> Deployment
    XProd --o Deployment
    Access --- Dot1
    Data --- Dot1
    Deployment --- Dot1
    SArg --- Dot1
    Dot1 --> Security
    XScope --o Security
```

### Package Access
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
    Access["<b>Access</b><br>User access control prevents unauthorized actions"]
    AAdmin["<b>AAdmin</b><br>Site administrators follow the published access management policy<br>ASSUMED"]
    SAccess[/"<b>SAccess</b><br>Access control is argued by examining authentication and authorization"/]
    AuthN["<b>AuthN</b><br>All users are authenticated before accessing protected resources"]
    AuthZ["<b>AuthZ</b><br>Users can only access resources appropriate to their role"]
    XSSFree["<b>XSSFree</b><br>Cross-site scripting attacks are mitigated"]
    SqlFree["<b>SqlFree</b><br>SQL injection attacks are mitigated<br>✗"]
    EvLogin[("<b>EvLogin</b>&nbsp;↗<br>Login audit log shows no unauthorized access in last 90 days")]
    JMechanism["<b>JMechanism</b><br>Password-plus-MFA provides industry-standard two-factor authentication"]
    XLogPolicy[("<b>XLogPolicy</b>&nbsp;↗<br>Log retention policy requires 90-day audit trail")]
    EvRBAC[("<b>EvRBAC</b>&nbsp;↗<br>Role-based access control configuration review passed")]
    AuthZAdmin["<b>AuthZAdmin</b><br>Administrative functions require elevated privilege<br>ASSUMED"]
    EvCSP[("<b>EvCSP</b>&nbsp;↗<br>Content Security Policy headers verified by automated scanner")]
    EvPenTest[("<b>EvPenTest</b>&nbsp;↗<br>Penetration test report identifies active vulnerabilities in multiple endpoints")]
    DBVuln["<b>DBVuln</b><br>Active SQL injection vulnerability found in search endpoint"]
    Dot1((" ")):::sacmDot
    Dot2((" ")):::sacmDot
    Dot3((" ")):::sacmDot
    Dot4((" ")):::sacmDot
    click Access "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-access"
    click AAdmin "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#assumption-aadmin"
    click SAccess "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#strategy-saccess"
    click AuthN "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-authn"
    click AuthZ "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-authz"
    click XSSFree "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-xssfree"
    click SqlFree "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-sqlfree"
    click EvLogin "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#evidence-evlogin"
    click JMechanism "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#justification-jmechanism"
    click XLogPolicy "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#context-xlogpolicy"
    click EvRBAC "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#evidence-evrbac"
    click AuthZAdmin "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-authzadmin"
    click EvCSP "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#evidence-evcsp"
    click EvPenTest "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#evidence-evpentest"
    click DBVuln "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-dbvuln"

    BottomPadding[ ]:::invisible ~~~ AAdmin
    BottomPadding ~~~ SAccess
    BottomPadding ~~~ EvLogin
    BottomPadding ~~~ JMechanism
    BottomPadding ~~~ XLogPolicy
    BottomPadding ~~~ EvRBAC
    BottomPadding ~~~ AuthZAdmin
    BottomPadding ~~~ EvCSP
    BottomPadding ~~~ EvPenTest
    BottomPadding ~~~ DBVuln
    EvLogin --- Dot1
    JMechanism --- Dot1
    Dot1 --> AuthN
    XLogPolicy --o AuthN
    EvRBAC --- Dot2
    AuthZAdmin --- Dot2
    Dot2 --> AuthZ
    EvCSP --> XSSFree
    EvPenTest --- Dot3
    DBVuln --- Dot3
    Dot3 -->|⊖| SqlFree
    AAdmin --- Dot4
    AuthN --- Dot4
    AuthZ --- Dot4
    XSSFree --- Dot4
    SqlFree --- Dot4
    SAccess --- Dot4
    Dot4 --> Access
```

### Package Data
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
    Data["<b>Data</b><br>Sensitive user data is protected in transit and at rest"]
    XRegulation[("<b>XRegulation</b>&nbsp;↗<br>GDPR and applicable state privacy laws govern data handling")]
    AEncrypt["<b>AEncrypt</b><br>TLS 1.3 is correctly deployed on all public endpoints<br>━━━"]
    SData[/"<b>SData</b><br>Data protection is argued by examining encryption, minimization, and audit logging"/]
    MetaClaim["<b>MetaClaim</b><br>This assurance case addresses all applicable data protection requirements"]
    Encrypt["<b>Encrypt</b><br>All sensitive data is encrypted in transit and at rest"]
    Minimise["<b>Minimise</b><br>Only necessary data is collected and retained per the privacy policy"]
    AuditAccess["<b>AuditAccess</b><br>All sensitive data access events are logged and periodically reviewed"]:::abstractClaim
    EvTLS[("<b>EvTLS</b>&nbsp;↗<br>TLS configuration scan achieves A+ rating")]
    EvDB[("<b>EvDB</b>&nbsp;↗<br>Database-level encryption enabled and key management audited")]
    DataMap["<b>DataMap</b><br>The data flow diagram covers all personal data stores and flows<br>..."]
    JRetention["<b>JRetention</b><br>Data minimisation reduces breach impact and aids regulatory compliance"]
    Dot1((" ")):::sacmDot
    Dot2((" ")):::sacmDot
    Dot3((" ")):::sacmDot
    click Data "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-data"
    click XRegulation "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#context-xregulation"
    click AEncrypt "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-aencrypt"
    click SData "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#strategy-sdata"
    click MetaClaim "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-metaclaim"
    click Encrypt "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-encrypt"
    click Minimise "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-minimise"
    click AuditAccess "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-auditaccess"
    click EvTLS "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#evidence-evtls"
    click EvDB "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#evidence-evdb"
    click DataMap "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-datamap"
    click JRetention "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#justification-jretention"

    BottomPadding[ ]:::invisible ~~~ XRegulation
    BottomPadding ~~~ AEncrypt
    BottomPadding ~~~ SData
    BottomPadding ~~~ MetaClaim
    BottomPadding ~~~ AuditAccess
    BottomPadding ~~~ EvTLS
    BottomPadding ~~~ EvDB
    BottomPadding ~~~ DataMap
    BottomPadding ~~~ JRetention
    EvTLS --- Dot1
    EvDB --- Dot1
    Dot1 --> Encrypt
    DataMap --- Dot2
    JRetention --- Dot2
    Dot2 --> Minimise
    AEncrypt --- Dot3
    Encrypt --- Dot3
    Minimise --- Dot3
    AuditAccess --- Dot3
    SData --- Dot3
    MetaClaim --- Dot3
    Dot3 --> Data
    XRegulation --o Data
```
<!-- end verocase -->

## GSN Diagrams

<!-- verocase gsn/mermaid * -->
### Package Security
```mermaid
---
config:
  theme: neutral
  flowchart:
    curve: basis
    htmlLabels: true
    rankSpacing: 60
    nodeSpacing: 45
    padding: 15
---
flowchart TD
    classDef invisible opacity:0
    classDef gsnUndev stroke-width:2px,stroke-dasharray: 5 5;
    classDef connector fill:none,stroke:#cccccc,stroke-width:1px;
    Security["<b>Security</b><br>The website is adequately secure against moderate threats"]
    XScope(["<b>XScope</b><br>OWASP Top Ten threat model defines the threat scope"])
    SArg[/"<b>SArg</b><br>Security is argued by examining access control, data protection, and deployment"/]
    Access[["<b>Access</b>"]]
    Data[["<b>Data</b>"]]
    Deployment["<b>Deployment</b><br>Deployment configuration follows security hardening guidelines"]
    EvHarden(("<b>EvHarden</b><br>Server hardening checklist completed and signed off"))
    XProd(["<b>XProd</b><br>Production environment enforces HTTPS-only connections"])
    click Security "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-security"
    click XScope "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#context-xscope"
    click SArg "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#strategy-sarg"
    click Access "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#package-access"
    click Data "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#package-data"
    click Deployment "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-deployment"
    click EvHarden "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#evidence-evharden"
    click XProd "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#context-xprod"

    Security --o XScope
    Security --> SArg
    SArg --> Access
    SArg --> Data
    SArg --> Deployment
    Deployment --> EvHarden
    Deployment --o XProd
    XScope ~~~ BottomPadding[ ]:::invisible
    Access ~~~ BottomPadding
    Data ~~~ BottomPadding
    EvHarden ~~~ BottomPadding
    XProd ~~~ BottomPadding
```

### Package Access
```mermaid
---
config:
  theme: neutral
  flowchart:
    curve: basis
    htmlLabels: true
    rankSpacing: 60
    nodeSpacing: 45
    padding: 15
---
flowchart TD
    classDef invisible opacity:0
    classDef gsnUndev stroke-width:2px,stroke-dasharray: 5 5;
    classDef connector fill:none,stroke:#cccccc,stroke-width:1px;
    Access["<b>Access</b><br>User access control prevents unauthorized actions"]
    AAdmin("<b>AAdmin</b>&nbsp;Ⓐ<br>Site administrators follow the published access management policy")
    SAccess[/"<b>SAccess</b><br>Access control is argued by examining authentication and authorization"/]
    AuthN["<b>AuthN</b><br>All users are authenticated before accessing protected resources"]
    AuthZ["<b>AuthZ</b><br>Users can only access resources appropriate to their role"]
    XSSFree["<b>XSSFree</b><br>Cross-site scripting attacks are mitigated"]
    SqlFree["<b>SqlFree</b><br>SQL injection attacks are mitigated<br>✗"]
    EvLogin(("<b>EvLogin</b><br>Login audit log shows no unauthorized access in last 90 days"))
    JMechanism("<b>JMechanism</b>&nbsp;Ⓙ<br>Password-plus-MFA provides industry-standard two-factor authentication")
    XLogPolicy(["<b>XLogPolicy</b><br>Log retention policy requires 90-day audit trail"])
    EvRBAC(("<b>EvRBAC</b><br>Role-based access control configuration review passed"))
    AuthZAdmin("<b>AuthZAdmin</b>&nbsp;Ⓐ<br>Administrative functions require elevated privilege")
    EvCSP(("<b>EvCSP</b><br>Content Security Policy headers verified by automated scanner"))
    EvPenTest(("<b>EvPenTest</b><br>Penetration test report identifies active vulnerabilities in multiple endpoints"))
    DBVuln["<b>DBVuln</b><br>Active SQL injection vulnerability found in search endpoint"]
    click Access "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-access"
    click AAdmin "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#assumption-aadmin"
    click SAccess "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#strategy-saccess"
    click AuthN "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-authn"
    click AuthZ "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-authz"
    click XSSFree "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-xssfree"
    click SqlFree "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-sqlfree"
    click EvLogin "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#evidence-evlogin"
    click JMechanism "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#justification-jmechanism"
    click XLogPolicy "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#context-xlogpolicy"
    click EvRBAC "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#evidence-evrbac"
    click AuthZAdmin "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-authzadmin"
    click EvCSP "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#evidence-evcsp"
    click EvPenTest "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#evidence-evpentest"
    click DBVuln "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-dbvuln"

    Access --o AAdmin
    Access --> SAccess
    SAccess --> AuthN
    AuthN --> EvLogin
    AuthN --o JMechanism
    AuthN --o XLogPolicy
    SAccess --> AuthZ
    AuthZ --> EvRBAC
    AuthZ --> AuthZAdmin
    SAccess --> XSSFree
    XSSFree --> EvCSP
    XSSFree -->|⊖| EvPenTest
    SAccess --> SqlFree
    SqlFree --> EvPenTest
    SqlFree -->|⊖| DBVuln
    AAdmin ~~~ BottomPadding[ ]:::invisible
    EvLogin ~~~ BottomPadding
    JMechanism ~~~ BottomPadding
    XLogPolicy ~~~ BottomPadding
    EvRBAC ~~~ BottomPadding
    AuthZAdmin ~~~ BottomPadding
    EvCSP ~~~ BottomPadding
    EvPenTest ~~~ BottomPadding
    DBVuln ~~~ BottomPadding
```

### Package Data
```mermaid
---
config:
  theme: neutral
  flowchart:
    curve: basis
    htmlLabels: true
    rankSpacing: 60
    nodeSpacing: 45
    padding: 15
---
flowchart TD
    classDef invisible opacity:0
    classDef gsnUndev stroke-width:2px,stroke-dasharray: 5 5;
    classDef connector fill:none,stroke:#cccccc,stroke-width:1px;
    Data["<b>Data</b><br>Sensitive user data is protected in transit and at rest"]
    XRegulation(["<b>XRegulation</b><br>GDPR and applicable state privacy laws govern data handling"])
    AEncrypt["<b>AEncrypt</b><br>TLS 1.3 is correctly deployed on all public endpoints<br>AXIOMATIC"]
    SData[/"<b>SData</b><br>Data protection is argued by examining encryption, minimization, and audit logging"/]
    MetaClaim["<b>MetaClaim</b><br>This assurance case addresses all applicable data protection requirements<br>METACLAIM"]
    Encrypt["<b>Encrypt</b><br>All sensitive data is encrypted in transit and at rest"]
    Minimise["<b>Minimise</b><br>Only necessary data is collected and retained per the privacy policy"]
    AuditAccess["<b>AuditAccess</b><br>All sensitive data access events are logged and periodically reviewed"]:::gsnUndev
    EvTLS(("<b>EvTLS</b><br>TLS configuration scan achieves A+ rating"))
    EvDB(("<b>EvDB</b><br>Database-level encryption enabled and key management audited"))
    DataMap["<b>DataMap</b><br>The data flow diagram covers all personal data stores and flows<br>◇"]
    JRetention("<b>JRetention</b>&nbsp;Ⓙ<br>Data minimisation reduces breach impact and aids regulatory compliance")
    click Data "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-data"
    click XRegulation "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#context-xregulation"
    click AEncrypt "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-aencrypt"
    click SData "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#strategy-sdata"
    click MetaClaim "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-metaclaim"
    click Encrypt "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-encrypt"
    click Minimise "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-minimise"
    click AuditAccess "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-auditaccess"
    click EvTLS "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#evidence-evtls"
    click EvDB "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#evidence-evdb"
    click DataMap "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-datamap"
    click JRetention "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#justification-jretention"

    Data --o XRegulation
    Data --> AEncrypt
    Data --> SData
    SData --> Encrypt
    Encrypt --> EvTLS
    Encrypt --> EvDB
    SData --> Minimise
    Minimise --> DataMap
    Minimise --o JRetention
    SData --> AuditAccess
    Data --> MetaClaim
    XRegulation ~~~ BottomPadding[ ]:::invisible
    AEncrypt ~~~ BottomPadding
    EvTLS ~~~ BottomPadding
    EvDB ~~~ BottomPadding
    DataMap ~~~ BottomPadding
    JRetention ~~~ BottomPadding
    AuditAccess ~~~ BottomPadding
    MetaClaim ~~~ BottomPadding
```
<!-- end verocase -->

## CAE Diagrams

<!-- verocase cae/mermaid * -->
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
    classDef invisible        opacity:0
    classDef connector        fill:none,stroke:#cccccc,stroke-width:1px
    classDef caeClaimClass    fill:#dce8f8,stroke:#2874a6,stroke-width:2px,color:#000
    classDef caeArgClass      fill:#fdebd0,stroke:#d35400,stroke-width:3px,color:#000
    classDef caeEvidClass     fill:#d5f5e3,stroke:#1e8449,stroke-width:2px,color:#000
    classDef caeInfoClass     fill:#f0f0f0,stroke:#999999,stroke-width:1px,stroke-dasharray:4 3,color:#000
    classDef caeAssumedClass  fill:#e8daef,stroke:#76448a,stroke-width:2px,stroke-dasharray:4 3,color:#000
    classDef caeSideClass     fill:#d6eaf8,stroke:#1a5276,stroke-width:2px,color:#000
    classDef caeDefeaterClass fill:#fadbd8,stroke:#c0392b,stroke-width:4px,color:#000
    classDef abstractClaim    stroke-width:2px,stroke-dasharray:5 5
    Security(("<b>Security</b><br>The website is adequately secure against moderate threats")):::caeClaimClass
    XScope(("<b>XScope</b><br>OWASP Top Ten threat model defines the threat scope")):::caeInfoClass
    SArg(["<b>SArg</b><br>Security is argued by examining access control, data protection, and deployment"]):::caeArgClass
    Access[["<b>Access</b>"]]:::caeClaimClass
    Data[["<b>Data</b>"]]:::caeClaimClass
    Deployment(("<b>Deployment</b><br>Deployment configuration follows security hardening guidelines")):::caeClaimClass
    EvHarden["<b>EvHarden</b><br>Server hardening checklist completed and signed off"]:::caeEvidClass
    XProd(("<b>XProd</b><br>Production environment enforces HTTPS-only connections")):::caeInfoClass
    click Security "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-security"
    click XScope "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#context-xscope"
    click SArg "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#strategy-sarg"
    click Access "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#package-access"
    click Data "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#package-data"
    click Deployment "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-deployment"
    click EvHarden "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#evidence-evharden"
    click XProd "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#context-xprod"

    BottomPadding[ ]:::invisible ~~~ Security
    Security -.-> XScope
    Security --> SArg
    SArg --> Access
    SArg --> Data
    SArg --> Deployment
    Deployment --> EvHarden
    Deployment -.-> XProd
```

### Package Access
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
    classDef invisible        opacity:0
    classDef connector        fill:none,stroke:#cccccc,stroke-width:1px
    classDef caeClaimClass    fill:#dce8f8,stroke:#2874a6,stroke-width:2px,color:#000
    classDef caeArgClass      fill:#fdebd0,stroke:#d35400,stroke-width:3px,color:#000
    classDef caeEvidClass     fill:#d5f5e3,stroke:#1e8449,stroke-width:2px,color:#000
    classDef caeInfoClass     fill:#f0f0f0,stroke:#999999,stroke-width:1px,stroke-dasharray:4 3,color:#000
    classDef caeAssumedClass  fill:#e8daef,stroke:#76448a,stroke-width:2px,stroke-dasharray:4 3,color:#000
    classDef caeSideClass     fill:#d6eaf8,stroke:#1a5276,stroke-width:2px,color:#000
    classDef caeDefeaterClass fill:#fadbd8,stroke:#c0392b,stroke-width:4px,color:#000
    classDef abstractClaim    stroke-width:2px,stroke-dasharray:5 5
    Access(("<b>Access</b><br>User access control prevents unauthorized actions")):::caeClaimClass
    AAdmin(("<b>AAdmin</b>&nbsp;Ⓐ<br>Site administrators follow the published access management policy")):::caeAssumedClass
    SAccess(["<b>SAccess</b><br>Access control is argued by examining authentication and authorization"]):::caeArgClass
    AuthN(("<b>AuthN</b><br>All users are authenticated before accessing protected resources")):::caeClaimClass
    AuthZ(("<b>AuthZ</b><br>Users can only access resources appropriate to their role")):::caeClaimClass
    XSSFree(("<b>XSSFree</b><br>Cross-site scripting attacks are mitigated")):::caeClaimClass
    SqlFree(("<b>SqlFree</b><br>SQL injection attacks are mitigated<br>DEFEATED")):::caeClaimClass
    EvLogin["<b>EvLogin</b><br>Login audit log shows no unauthorized access in last 90 days"]:::caeEvidClass
    JMechanism(["<b>JMechanism</b>&nbsp;Ⓢ<br>Password-plus-MFA provides industry-standard two-factor authentication"]):::caeSideClass
    XLogPolicy(("<b>XLogPolicy</b><br>Log retention policy requires 90-day audit trail")):::caeInfoClass
    EvRBAC["<b>EvRBAC</b><br>Role-based access control configuration review passed"]:::caeEvidClass
    AuthZAdmin(("<b>AuthZAdmin</b>&nbsp;Ⓐ<br>Administrative functions require elevated privilege")):::caeAssumedClass
    EvCSP["<b>EvCSP</b><br>Content Security Policy headers verified by automated scanner"]:::caeEvidClass
    EvPenTest["<b>EvPenTest</b><br>Penetration test report identifies active vulnerabilities in multiple endpoints"]:::caeEvidClass
    DBVuln(("<b>DBVuln</b>&nbsp;⊗<br>Active SQL injection vulnerability found in search endpoint")):::caeDefeaterClass
    click Access "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-access"
    click AAdmin "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#assumption-aadmin"
    click SAccess "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#strategy-saccess"
    click AuthN "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-authn"
    click AuthZ "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-authz"
    click XSSFree "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-xssfree"
    click SqlFree "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-sqlfree"
    click EvLogin "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#evidence-evlogin"
    click JMechanism "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#justification-jmechanism"
    click XLogPolicy "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#context-xlogpolicy"
    click EvRBAC "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#evidence-evrbac"
    click AuthZAdmin "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-authzadmin"
    click EvCSP "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#evidence-evcsp"
    click EvPenTest "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#evidence-evpentest"
    click DBVuln "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-dbvuln"

    BottomPadding[ ]:::invisible ~~~ Access
    Access --> AAdmin
    Access --> SAccess
    SAccess --> AuthN
    AuthN --> EvLogin
    AuthN --> JMechanism
    AuthN -.-> XLogPolicy
    SAccess --> AuthZ
    AuthZ --> EvRBAC
    AuthZ --> AuthZAdmin
    SAccess --> XSSFree
    XSSFree --> EvCSP
    XSSFree -->|⊖| EvPenTest
    SAccess --> SqlFree
    SqlFree --> EvPenTest
    SqlFree --x DBVuln
```

### Package Data
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
    classDef invisible        opacity:0
    classDef connector        fill:none,stroke:#cccccc,stroke-width:1px
    classDef caeClaimClass    fill:#dce8f8,stroke:#2874a6,stroke-width:2px,color:#000
    classDef caeArgClass      fill:#fdebd0,stroke:#d35400,stroke-width:3px,color:#000
    classDef caeEvidClass     fill:#d5f5e3,stroke:#1e8449,stroke-width:2px,color:#000
    classDef caeInfoClass     fill:#f0f0f0,stroke:#999999,stroke-width:1px,stroke-dasharray:4 3,color:#000
    classDef caeAssumedClass  fill:#e8daef,stroke:#76448a,stroke-width:2px,stroke-dasharray:4 3,color:#000
    classDef caeSideClass     fill:#d6eaf8,stroke:#1a5276,stroke-width:2px,color:#000
    classDef caeDefeaterClass fill:#fadbd8,stroke:#c0392b,stroke-width:4px,color:#000
    classDef abstractClaim    stroke-width:2px,stroke-dasharray:5 5
    Data(("<b>Data</b><br>Sensitive user data is protected in transit and at rest")):::caeClaimClass
    XRegulation(("<b>XRegulation</b><br>GDPR and applicable state privacy laws govern data handling")):::caeInfoClass
    AEncrypt(("<b>AEncrypt</b><br>TLS 1.3 is correctly deployed on all public endpoints")):::caeClaimClass
    SData(["<b>SData</b><br>Data protection is argued by examining encryption, minimization, and audit logging"]):::caeArgClass
    MetaClaim(("<b>MetaClaim</b><br>This assurance case addresses all applicable data protection requirements")):::caeClaimClass
    Encrypt(("<b>Encrypt</b><br>All sensitive data is encrypted in transit and at rest")):::caeClaimClass
    Minimise(("<b>Minimise</b><br>Only necessary data is collected and retained per the privacy policy")):::caeClaimClass
    AuditAccess(("<b>AuditAccess</b><br>All sensitive data access events are logged and periodically reviewed")):::caeClaimClass:::abstractClaim
    EvTLS["<b>EvTLS</b><br>TLS configuration scan achieves A+ rating"]:::caeEvidClass
    EvDB["<b>EvDB</b><br>Database-level encryption enabled and key management audited"]:::caeEvidClass
    DataMap(("<b>DataMap</b><br>The data flow diagram covers all personal data stores and flows<br>...")):::caeClaimClass
    JRetention(["<b>JRetention</b>&nbsp;Ⓢ<br>Data minimisation reduces breach impact and aids regulatory compliance"]):::caeSideClass
    click Data "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-data"
    click XRegulation "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#context-xregulation"
    click AEncrypt "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-aencrypt"
    click SData "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#strategy-sdata"
    click MetaClaim "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-metaclaim"
    click Encrypt "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-encrypt"
    click Minimise "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-minimise"
    click AuditAccess "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-auditaccess"
    click EvTLS "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#evidence-evtls"
    click EvDB "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#evidence-evdb"
    click DataMap "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#claim-datamap"
    click JRetention "https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/demo-output.expected.md#justification-jretention"

    BottomPadding[ ]:::invisible ~~~ Data
    Data -.-> XRegulation
    Data --> AEncrypt
    Data --> SData
    SData --> Encrypt
    Encrypt --> EvTLS
    Encrypt --> EvDB
    SData --> Minimise
    Minimise --> DataMap
    Minimise --> JRetention
    SData --> AuditAccess
    Data --> MetaClaim
```
<!-- end verocase -->

## LTAC Notation

<!-- verocase ltac/markdown * -->
### Package Security
- [Claim Security: The website is adequately secure against moderate threats](#claim-security)
  - [Context XScope: OWASP Top Ten threat model defines the threat scope](#context-xscope) ([owasp-top10.pdf](owasp-top10.pdf))
  - [Strategy SArg: Security is argued by examining access control, data protection, and deployment](#strategy-sarg)
    - [Claim Access](#claim-access)
    - [Claim Data](#claim-data)
    - [Claim Deployment: Deployment configuration follows security hardening guidelines](#claim-deployment)
      - [Evidence EvHarden: Server hardening checklist completed and signed off](#evidence-evharden) ([hardening-checklist.pdf](hardening-checklist.pdf))
      - [Context XProd: Production environment enforces HTTPS-only connections](#context-xprod)

### Package Access
- [Claim Access: User access control prevents unauthorized actions](#claim-access)
  - [Assumption AAdmin: Site administrators follow the published access management policy](#assumption-aadmin)
  - [Strategy SAccess: Access control is argued by examining authentication and authorization](#strategy-saccess)
    - [Claim AuthN: All users are authenticated before accessing protected resources](#claim-authn)
      - [Evidence EvLogin: Login audit log shows no unauthorized access in last 90 days](#evidence-evlogin) ([audit.log](audit.log))
      - [Justification JMechanism: Password-plus-MFA provides industry-standard two-factor authentication](#justification-jmechanism)
      - [Context XLogPolicy: Log retention policy requires 90-day audit trail](#context-xlogpolicy) ([log-policy.pdf](log-policy.pdf))
    - [Claim AuthZ: Users can only access resources appropriate to their role](#claim-authz)
      - [Evidence EvRBAC: Role-based access control configuration review passed](#evidence-evrbac) ([rbac-review.pdf](rbac-review.pdf))
      - [Claim AuthZAdmin: Administrative functions require elevated privilege](#claim-authzadmin)
    - [Claim XSSFree: Cross-site scripting attacks are mitigated](#claim-xssfree)
      - [Evidence EvCSP: Content Security Policy headers verified by automated scanner](#evidence-evcsp) ([csp-scan.pdf](csp-scan.pdf))
      - [Relation R1](#relation-r1)
    - [Claim SqlFree: SQL injection attacks are mitigated](#claim-sqlfree)
      - [Evidence EvPenTest: Penetration test report identifies active vulnerabilities in multiple endpoints](#evidence-evpentest) ([pentest-2024.pdf](pentest-2024.pdf))
      - [Claim DBVuln: Active SQL injection vulnerability found in search endpoint](#claim-dbvuln)

### Package Data
- [Claim Data: Sensitive user data is protected in transit and at rest](#claim-data)
  - [Context XRegulation: GDPR and applicable state privacy laws govern data handling](#context-xregulation) ([privacy-policy.pdf](privacy-policy.pdf))
  - [Claim AEncrypt: TLS 1.3 is correctly deployed on all public endpoints](#claim-aencrypt)
  - [Strategy SData: Data protection is argued by examining encryption, minimization, and audit logging](#strategy-sdata)
    - [Claim Encrypt: All sensitive data is encrypted in transit and at rest](#claim-encrypt)
      - [Evidence EvTLS: TLS configuration scan achieves A+ rating](#evidence-evtls) ([ssl-labs-report.pdf](ssl-labs-report.pdf))
      - [Evidence EvDB: Database-level encryption enabled and key management audited](#evidence-evdb) ([db-audit.pdf](db-audit.pdf))
    - [Claim Minimise: Only necessary data is collected and retained per the privacy policy](#claim-minimise)
      - [Claim DataMap: The data flow diagram covers all personal data stores and flows](#claim-datamap)
      - [Justification JRetention: Data minimisation reduces breach impact and aids regulatory compliance](#justification-jretention)
    - [Claim AuditAccess: All sensitive data access events are logged and periodically reviewed](#claim-auditaccess)
  - [Claim MetaClaim: This assurance case addresses all applicable data protection requirements](#claim-metaclaim)
<!-- end verocase -->

## Element Details

<!-- verocase element Security -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="claim-security"></a>
### Claim Security: The website is adequately secure against moderate threats

Referenced by: **[Package Security](#package-security)**

Supported by: **[Context XScope](#context-xscope)**, [Strategy SArg](#strategy-sarg)
<!-- end verocase -->

The website must withstand opportunistic attacks and targeted attacks up to
the level described by the OWASP Top Ten threat model. This is the
top-level claim the entire assurance case supports.

<!-- verocase element XScope -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="context-xscope"></a>
### Context XScope: OWASP Top Ten threat model defines the threat scope

Referenced by: **[Package Security](#package-security)**

Supports: **[Claim Security](#claim-security)**

External Reference: [owasp-top10.pdf](https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/owasp-top10.pdf)
<!-- end verocase -->

OWASP Top Ten is a widely recognised baseline threat model for public-facing
web applications, updated annually to reflect current attacker techniques.
It was agreed with the customer as the applicable scope for this engagement.

<!-- verocase element SArg -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="strategy-sarg"></a>
### Strategy SArg: Security is argued by examining access control, data protection, and deployment

Referenced by: **[Package Security](#package-security)**

Supported by: **[Claim Access](#claim-access)**, [Claim Data](#claim-data), [Claim Deployment](#claim-deployment)

Supports: **[Claim Security](#claim-security)**
<!-- end verocase -->

The argument is decomposed into three parallel sub-arguments. Access control,
data protection, and deployment configuration are argued independently; each
sub-argument supports the top-level security claim.

<!-- verocase element Access -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="claim-access"></a>
### Claim Access: User access control prevents unauthorized actions

Referenced by: **[Package Access](#package-access)**, [Package Security](#package-security)

Supported by: **[Assumption AAdmin](#assumption-aadmin)**, [Strategy SAccess](#strategy-saccess)

Supports: [Strategy SArg](#strategy-sarg)
<!-- end verocase -->

This claim covers the mechanisms that prevent unauthorised users from
reading, modifying, or destroying resources. It encompasses authentication,
authorisation, and protection against client-side injection attacks.

<!-- verocase element AAdmin -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="assumption-aadmin"></a>
### Assumption AAdmin: Site administrators follow the published access management policy

Referenced by: **[Package Access](#package-access)**

Supports: **[Claim Access](#claim-access)**
<!-- end verocase -->

Administrators are responsible for creating and revoking accounts, assigning
roles, and following the access management policy. Deliberate misuse by
administrators is outside the threat model for this case.

<!-- verocase element SAccess -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="strategy-saccess"></a>
### Strategy SAccess: Access control is argued by examining authentication and authorization

Referenced by: **[Package Access](#package-access)**

Supported by: **[Claim AuthN](#claim-authn)**, [Claim AuthZ](#claim-authz), [Claim XSSFree](#claim-xssfree), [Claim SqlFree](#claim-sqlfree)

Supports: **[Claim Access](#claim-access)**
<!-- end verocase -->

Access control is argued by examining the authentication mechanism,
role-based authorisation configuration, and mitigations for the two most
prevalent web injection attack classes: XSS and SQL injection.

<!-- verocase element AuthN -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="claim-authn"></a>
### Claim AuthN: All users are authenticated before accessing protected resources

Referenced by: **[Package Access](#package-access)**

Supported by: **[Evidence EvLogin](#evidence-evlogin)**, [Justification JMechanism](#justification-jmechanism), [Context XLogPolicy](#context-xlogpolicy)

Supports: **[Strategy SAccess](#strategy-saccess)**
<!-- end verocase -->

All accounts require a password and a time-based one-time password (TOTP)
token before a session is established. Failed attempts trigger a progressive
delay and are recorded in the audit log.

<!-- verocase element EvLogin -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="evidence-evlogin"></a>
### Evidence EvLogin: Login audit log shows no unauthorized access in last 90 days

Referenced by: **[Package Access](#package-access)**

Supports: **[Claim AuthN](#claim-authn)**

External Reference: [audit.log](https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/audit.log)
<!-- end verocase -->

Login audit logs for the preceding 90 days were reviewed. No sessions were
established without a successful MFA challenge, and no accounts showed
anomalous access patterns.

<!-- verocase element JMechanism -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="justification-jmechanism"></a>
### Justification JMechanism: Password-plus-MFA provides industry-standard two-factor authentication

Referenced by: **[Package Access](#package-access)**

Supports: **[Claim AuthN](#claim-authn)**
<!-- end verocase -->

Password-plus-TOTP corresponds to NIST SP 800-63B AAL2, the recommended
assurance level for applications handling personal data. It defends against
both password-stuffing attacks and phished credentials.

<!-- verocase element XLogPolicy -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="context-xlogpolicy"></a>
### Context XLogPolicy: Log retention policy requires 90-day audit trail

Referenced by: **[Package Access](#package-access)**

Supports: **[Claim AuthN](#claim-authn)**

External Reference: [log-policy.pdf](https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/log-policy.pdf)
<!-- end verocase -->

The log retention policy requires all authentication events to be retained
for a minimum of 90 days, satisfying the audit window needed to detect
slow-burn credential-abuse campaigns.

<!-- verocase element AuthZ -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="claim-authz"></a>
### Claim AuthZ: Users can only access resources appropriate to their role

Referenced by: **[Package Access](#package-access)**

Supported by: **[Evidence EvRBAC](#evidence-evrbac)**, [Claim AuthZAdmin](#claim-authzadmin)

Supports: **[Strategy SAccess](#strategy-saccess)**
<!-- end verocase -->

Permissions are assigned by role; no user is granted capabilities beyond
those their role requires. Role assignments are reviewed quarterly by the
access control team and approved by the relevant department head.

<!-- verocase element EvRBAC -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="evidence-evrbac"></a>
### Evidence EvRBAC: Role-based access control configuration review passed

Referenced by: **[Package Access](#package-access)**

Supports: **[Claim AuthZ](#claim-authz)**

External Reference: [rbac-review.pdf](https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/rbac-review.pdf)
<!-- end verocase -->

An independent configuration review compared the RBAC policy document
against the live permission tables. No over-privileged accounts or role
violations were found.

<!-- verocase element AuthZAdmin -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="claim-authzadmin"></a>
### Claim AuthZAdmin: Administrative functions require elevated privilege

Referenced by: **[Package Access](#package-access)**

Supports: **[Claim AuthZ](#claim-authz)**
<!-- end verocase -->

Elevated administrative actions require the operator to re-authenticate into
a separate privileged session with a short timeout. This architectural
control is assumed to be correctly enforced by the framework.

<!-- verocase element XSSFree -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="claim-xssfree"></a>
### Claim XSSFree: Cross-site scripting attacks are mitigated

Referenced by: **[Package Access](#package-access)**

Supported by: **[Evidence EvCSP](#evidence-evcsp)**, [Relation R1](#relation-r1)

Supports: **[Strategy SAccess](#strategy-saccess)**
<!-- end verocase -->

Cross-site scripting is mitigated through a Content Security Policy that
blocks inline scripts and restricts script sources, combined with
context-aware output encoding on all dynamic content.

<!-- verocase element EvCSP -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="evidence-evcsp"></a>
### Evidence EvCSP: Content Security Policy headers verified by automated scanner

Referenced by: **[Package Access](#package-access)**

Supports: **[Claim XSSFree](#claim-xssfree)**

External Reference: [csp-scan.pdf](https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/csp-scan.pdf)
<!-- end verocase -->

An automated CSP scanner confirmed that policy headers are present on all
public endpoints and that the policy is sufficiently restrictive to block
known inline-script injection patterns.

<!-- verocase element R1 -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="relation-r1"></a>
### Relation R1

Referenced by: **[Package Access](#package-access)**

Supported by: **[Evidence EvPenTest](#evidence-evpentest)**

Supports: **[Claim XSSFree](#claim-xssfree)**
<!-- end verocase -->

The penetration test found XSS vulnerabilities on several endpoints that
lack consistent output encoding, indicating that the mitigations are not
uniformly applied. This is cited as a counter-argument to XSSFree.

<!-- verocase element SqlFree -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="claim-sqlfree"></a>
### Claim SqlFree: SQL injection attacks are mitigated

Referenced by: **[Package Access](#package-access)**

Supported by: **[Evidence EvPenTest](#evidence-evpentest)**, [Claim DBVuln](#claim-dbvuln)

Supports: **[Strategy SAccess](#strategy-saccess)**
<!-- end verocase -->

SQL injection was intended to be prevented through an ORM layer and
mandatory use of parameterised queries. However, a penetration test
revealed a legacy code path that bypasses the ORM, making this claim
defeated: remediation is required before the case can be reasserted.

<!-- verocase element EvPenTest -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="evidence-evpentest"></a>
### Evidence EvPenTest: Penetration test report identifies active vulnerabilities in multiple endpoints

Referenced by: **[Package Access](#package-access)**

Supports: **[Claim SqlFree](#claim-sqlfree)**, [Relation R1](#relation-r1)

External Reference: [pentest-2024.pdf](https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/pentest-2024.pdf)
<!-- end verocase -->

A targeted penetration test was conducted against the application by an
external security firm. The report identified an actively exploitable SQL
injection vulnerability in the search endpoint (severity: Critical) and
flagged multiple endpoints with inconsistent XSS output encoding.

<!-- verocase element DBVuln -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="claim-dbvuln"></a>
### Claim DBVuln: Active SQL injection vulnerability found in search endpoint

Referenced by: **[Package Access](#package-access)**

Supports: **[Claim SqlFree](#claim-sqlfree)**
<!-- end verocase -->

The search endpoint constructs a query by string concatenation when the
ORM cache misses, admitting direct SQL injection. This vulnerability
defeats the SqlFree claim and must be remediated before the assurance
case can be reasserted.

<!-- verocase element Data -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="claim-data"></a>
### Claim Data: Sensitive user data is protected in transit and at rest

Referenced by: **[Package Data](#package-data)**, [Package Security](#package-security)

Supported by: **[Context XRegulation](#context-xregulation)**, [Claim AEncrypt](#claim-aencrypt), [Strategy SData](#strategy-sdata), [Claim MetaClaim](#claim-metaclaim)

Supports: [Strategy SArg](#strategy-sarg)
<!-- end verocase -->

Personal data collected by the application must be protected against
disclosure and tampering both in transit (over the network) and at rest
(in the database and backups). Handling must comply with applicable
privacy regulations.

<!-- verocase element XRegulation -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="context-xregulation"></a>
### Context XRegulation: GDPR and applicable state privacy laws govern data handling

Referenced by: **[Package Data](#package-data)**

Supports: **[Claim Data](#claim-data)**

External Reference: [privacy-policy.pdf](https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/privacy-policy.pdf)
<!-- end verocase -->

GDPR and applicable state privacy laws impose obligations on data
collection, processing, retention, and breach notification. The privacy
policy covering these obligations has been reviewed by legal counsel.

<!-- verocase element AEncrypt -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="claim-aencrypt"></a>
### Claim AEncrypt: TLS 1.3 is correctly deployed on all public endpoints

Referenced by: **[Package Data](#package-data)**

Supports: **[Claim Data](#claim-data)**
<!-- end verocase -->

The correctness of the TLS 1.3 protocol itself is taken as axiomatic,
established by the IETF specification (RFC 8446) and extensive
cryptographic review. This case argues only that TLS 1.3 is correctly
deployed, not that the protocol is sound.

<!-- verocase element SData -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="strategy-sdata"></a>
### Strategy SData: Data protection is argued by examining encryption, minimization, and audit logging

Referenced by: **[Package Data](#package-data)**

Supported by: **[Claim Encrypt](#claim-encrypt)**, [Claim Minimise](#claim-minimise), [Claim AuditAccess](#claim-auditaccess)

Supports: **[Claim Data](#claim-data)**
<!-- end verocase -->

Data protection is argued across four concerns: encryption of data in
transit, encryption of data at rest, minimisation of data collected and
retained, and audit logging of access to sensitive records.

<!-- verocase element Encrypt -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="claim-encrypt"></a>
### Claim Encrypt: All sensitive data is encrypted in transit and at rest

Referenced by: **[Package Data](#package-data)**

Supported by: **[Evidence EvTLS](#evidence-evtls)**, [Evidence EvDB](#evidence-evdb)

Supports: **[Strategy SData](#strategy-sdata)**
<!-- end verocase -->

All external connections use TLS 1.3 with HSTS enforced. Database
volumes are encrypted with AES-256-GCM; encryption keys are stored in a
hardware security module and rotated annually.

<!-- verocase element EvTLS -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="evidence-evtls"></a>
### Evidence EvTLS: TLS configuration scan achieves A+ rating

Referenced by: **[Package Data](#package-data)**

Supports: **[Claim Encrypt](#claim-encrypt)**

External Reference: [ssl-labs-report.pdf](https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/ssl-labs-report.pdf)
<!-- end verocase -->

An SSL Labs scan awarded the application an A+ rating, confirming correct
cipher-suite selection, HSTS preloading, and OCSP stapling on all
public-facing endpoints.

<!-- verocase element EvDB -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="evidence-evdb"></a>
### Evidence EvDB: Database-level encryption enabled and key management audited

Referenced by: **[Package Data](#package-data)**

Supports: **[Claim Encrypt](#claim-encrypt)**

External Reference: [db-audit.pdf](https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/db-audit.pdf)
<!-- end verocase -->

An independent database audit confirmed that encryption-at-rest is enabled
for all volumes containing personal data and that key management procedures
comply with the organisation's cryptographic standards policy.

<!-- verocase element Minimise -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="claim-minimise"></a>
### Claim Minimise: Only necessary data is collected and retained per the privacy policy

Referenced by: **[Package Data](#package-data)**

Supported by: **[Claim DataMap](#claim-datamap)**, [Justification JRetention](#justification-jretention)

Supports: **[Strategy SData](#strategy-sdata)**
<!-- end verocase -->

The application collects only fields required for the stated service
purpose. Retention schedules are enforced by an automated purge job that
runs nightly and is monitored for failures.

<!-- verocase element DataMap -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="claim-datamap"></a>
### Claim DataMap: The data flow diagram covers all personal data stores and flows

Referenced by: **[Package Data](#package-data)**

Supports: **[Claim Minimise](#claim-minimise)**
<!-- end verocase -->

The data flow diagram captures all personal data inputs, stores, processing
steps, and outputs. It has been drafted but formal sign-off from the data
protection officer is pending; this claim is therefore marked as needing
further support.

<!-- verocase element JRetention -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="justification-jretention"></a>
### Justification JRetention: Data minimisation reduces breach impact and aids regulatory compliance

Referenced by: **[Package Data](#package-data)**

Supports: **[Claim Minimise](#claim-minimise)**
<!-- end verocase -->

Collecting and retaining only the minimum necessary data reduces the impact
of a breach (less data exposed), simplifies compliance with GDPR Article
5(1)(e) (storage limitation), and lowers the cost of subject-access-request
responses.

<!-- verocase element AuditAccess -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="claim-auditaccess"></a>
### Claim AuditAccess: All sensitive data access events are logged and periodically reviewed

Referenced by: **[Package Data](#package-data)**

Supports: **[Strategy SData](#strategy-sdata)**
<!-- end verocase -->

Every read or write to a sensitive data record is appended to an
append-only audit log. The security team reviews the log for anomalous
patterns; the review cadence and escalation procedures are defined in the
forthcoming access monitoring policy, which has not yet been finalised.

<!-- verocase element MetaClaim -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="claim-metaclaim"></a>
### Claim MetaClaim: This assurance case addresses all applicable data protection requirements

Referenced by: **[Package Data](#package-data)**

Supports: **[Claim Data](#claim-data)**
<!-- end verocase -->

The data protection sub-argument was structured against the GDPR compliance
checklist. Each checklist item maps to at least one claim or evidence
element in the case, ensuring no data protection requirement is
inadvertently omitted.

<!-- verocase element Deployment -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="claim-deployment"></a>
### Claim Deployment: Deployment configuration follows security hardening guidelines

Referenced by: **[Package Security](#package-security)**

Supported by: **[Evidence EvHarden](#evidence-evharden)**, [Context XProd](#context-xprod)

Supports: **[Strategy SArg](#strategy-sarg)**
<!-- end verocase -->

The server configuration is derived from the CIS Benchmark hardening
profile for the operating system and is enforced via infrastructure-as-code.
Drift from the baseline triggers an automated alert.

<!-- verocase element EvHarden -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="evidence-evharden"></a>
### Evidence EvHarden: Server hardening checklist completed and signed off

Referenced by: **[Package Security](#package-security)**

Supports: **[Claim Deployment](#claim-deployment)**

External Reference: [hardening-checklist.pdf](https://github.com/david-a-wheeler/verocase/blob/main/tests/fixtures/hardening-checklist.pdf)
<!-- end verocase -->

The server hardening checklist was completed and signed off by the
infrastructure security team. The review covered OS-level patches, removal
of unnecessary services, firewall ingress rules, and file-permission
hardening.

<!-- verocase element XProd -->
<!-- DO NOT EDIT text from here until "end verocase" -->

<a id="context-xprod"></a>
### Context XProd: Production environment enforces HTTPS-only connections

Referenced by: **[Package Security](#package-security)**

Supports: **[Claim Deployment](#claim-deployment)**
<!-- end verocase -->

The production environment is configured to reject plain HTTP connections.
HTTP requests are redirected to HTTPS at the load balancer before reaching
any application code, preventing accidental cleartext transmission.
