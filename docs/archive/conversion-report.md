# Conversion Report: BadgeApp Assurance Case to caseproc

## Executive Summary

The BadgeApp assurance case (`bp-docs/assurance-case.md`) is a 3,852-line traditional
markdown document that justifies why the BadgeApp (CII Best Practices Badge application)
is adequately secure.  Converting it to caseproc form will require two new files:
a `case.ltac` containing the argument structure and a `case.md` that embeds the
existing detailed text alongside auto-generated caseproc regions.

The conversion is non-trivial but well-structured.  The document's section headings
map cleanly onto LTAC packages and Claims.  Most of the evidence exists only in text,
not in the existing figures, which simplifies extraction.

---

## 1. The Source Material

### 1.1 Overall structure

The document is organized around a single top-level claim:
> *The BadgeApp is adequately secure.*

The argument is decomposed by **ISO/IEC/IEEE 12207 software lifecycle processes**,
a deliberate "defense-in-breadth" strategy.  The top-level decomposition produces
roughly ten second-level claims, each of which is further decomposed.

Top-level sections (each likely maps to one or more LTAC packages):

| Section heading | Approximate LTAC package name |
|---|---|
| Security Requirements | `SecReqs` |
| Security in Design | `Design` |
| Security in Implementation | `Implementation` |
| Security in Integration and Verification | `Verification` |
| Transition and Operation | `Operations` |
| Maintenance | `Maintenance` |
| Acquisition Process | `Acquisition` |
| Infrastructure Management | `Infrastructure` |
| Human Resource Management | `HumanResources` |
| Project Planning / Risk / QA / Config Mgmt | `ProjectMgmt` |
| Certifications and Controls | `Certifications` |

### 1.2 Existing graphical structure

The claim/argument structure is encoded in `.odg` (LibreOffice Draw) files and
exported to `.png`/`.svg`.  These are **the primary source for LTAC structure**:

| File | Content | Notation |
|---|---|---|
| `assurance-case.odg` / `.png` | Top-level summary | CAE |
| `assurance-case-lifecycle.odg` / `.png` | Lifecycle processes | CAE |
| `assurance-case-implementation.odg` / `.png` | Implementation detail | CAE |
| `assurance-case-other-lifecycle.odg` / `.png` | Other lifecycle processes | CAE |
| `assurance-case-verification.odg` / `.png` | Verification | CAE |
| `assurance-case-toplevel-sacm.odg` / `.svg` | Top level (partial SACM) | SACM |
| `design.odg` / `.png` | Architecture diagram | N/A (informational) |

The top-level SACM diagram (`assurance-case-toplevel-sacm.svg`) is the most
up-to-date structural description.  The remaining `.odg` files are still in CAE.

### 1.3 CAE → LTAC element mapping

| CAE | LTAC | Notes |
|---|---|---|
| Claim / Subclaim (oval) | `Claim` | Direct mapping |
| Argument (rounded rect) | `Strategy` | CAE "Argument" = LTAC "Strategy" |
| Evidence (rectangle) | `Evidence` | Direct mapping |
| *(no CAE Context)* | `Context` | Use for scope / env info |
| *(no CAE Assumption)* | `Assumption` | Use for accepted-without-proof claims |

The existing SACM-notation diagram uses Claims and ArgumentReasonings, which map
to `Claim` and `Strategy` respectively—no translation needed for that diagram.

### 1.4 Evidence location

Most evidence is **not shown in the figures**.  Instead it is documented exclusively
in the prose sections of `assurance-case.md` (code pointers, test names, config
files, external references).  This is noted by the document itself:

> "We do not show most evidence in the figures, but provide the evidence in
> the supporting text below instead, because large figures are time-consuming to edit."

This means that creating LTAC `Evidence` elements will largely be a **text-mining
task** on `assurance-case.md`, not a figure-reading task.

### 1.5 Document depth

The document is deep.  A few sampled sections show 3–5 levels of claim nesting.
For example:

```
Top claim: BadgeApp is adequately secure
  Claim: Security requirements identified & met
    Claim: Confidentiality requirements met
      Claim: User privacy maintained
        Claim: No third-party tracking embedded
          Evidence: CSP policy (source code ref)
          Evidence: No external JS/font refs (code inspection)
        Claim: Email is privacy-respecting
          Evidence: SendGrid tracker settings (code ref)
      Claim: Non-public data kept confidential
        ...
```

The `##` / `###` / `####` heading hierarchy in the markdown document directly
encodes most of this nesting, making semi-automated conversion feasible.

---

## 2. caseproc Format Requirements

### 2.1 case.ltac

- One or more packages, each starting with a `Claim` at indent level 0.
- 2 spaces per indent level; every non-blank line is an element.
- Blank line separates packages.
- Cross-package citations use `^ID` (identifier declared in another package).
- All identifiers must be globally unique across the whole file.
- `{needsSupport}` marks leaf claims that still need sub-claims or evidence.

### 2.2 case.md

- Freeform markdown; caseproc only touches content **between** its markers:
  ```
  <!-- caseproc ... -->
  <!-- end caseproc -->
  ```
- `<!-- caseproc package * -->` inserts auto-generated headings, diagrams, and
  hyperlinks for every package — a useful default for a first pass.
- `<!-- caseproc element ID -->` inserts a rendered view of a single element.
- Individual `<!-- caseproc element ID -->` regions allow prose detail to be
  placed immediately after each element's auto-generated diagram node.

### 2.3 Identifiers

Good identifier conventions for this case:
- Top-level claim per package: `BadgeApp`, `SecReqs`, `Design`, etc.
- Sub-claims follow a hierarchical naming scheme, e.g., `Confidentiality`,
  `UserPrivacy`, `NoThirdPartyTracking`.
- Strategies: prefix `S-`, e.g., `S-ByLifecycle`.
- Evidence: prefix `Ev-`, e.g., `Ev-CSP`.
- Contexts: prefix `X-`, e.g., `X-ISO12207`.
- Meaningful names are preferred over GSN-style `G1`, `G2` for a case this large,
  because the identifier is the main navigation anchor in a long LTAC file.

---

## 3. Proposed Conversion Plan

The conversion is staged to prevent data loss and to allow validation at each step.

### Stage 1 — Header-only skeleton (minimal change, maximum safety)

**Goal**: Get `case.md` and `case.ltac` created without losing any existing prose.

Steps:
1. Copy `bp-docs/assurance-case.md` to `case.md` (or keep it in `bp-docs/` and
   point caseproc at it; the latter avoids moving files mid-conversion).
2. Create a `case.ltac` that has **one package per major figure** (5–6 packages
   matching the existing `.odg` files) with:
   - A top-level `Claim` for each package.
   - Only one or two levels of sub-claims, matching the `##`/`###` heading structure.
   - All leaf claims marked `{needsSupport}`.
3. In `case.md`, **replace the existing figure references** (the `![...](...)` lines)
   with `<!-- caseproc package PKG-ID -->` / `<!-- end caseproc -->` blocks.
4. Run `caseproc` to validate the LTAC and regenerate the figure regions.

**Deliverable**: A working caseproc project where caseproc-generated diagrams
replace the static `.png` embeds, but all prose is unchanged.

**Risk**: Low.  The prose text is untouched.  Only the figure section changes.

### Stage 2 — Extract claim structure from .odg files

**Goal**: Populate the LTAC with the full claim/argument tree from each diagram.

Steps:
1. Open each `.odg` file and manually read out the claim/argument hierarchy
   (the SVG text content of `assurance-case-toplevel-sacm.svg` is readable directly;
   for the `.odg` files, LibreOffice or conversion to SVG can help).
2. Translate CAE nodes to LTAC elements:
   - Oval → `Claim`
   - Rounded rect → `Strategy`
   - Rectangle → `Evidence`
3. Add cross-package citations (`^ID`) where a sub-claim in one package's figure
   refers to a claim elaborated in another package.
4. Keep `{needsSupport}` on any claims that still have no sub-claims/evidence.
5. Run `caseproc --validate` after each package to catch errors early.

**Deliverable**: Full claim/argument structure in LTAC; auto-generated Mermaid
diagrams replace the static `.png` figures.

**Risk**: Low–Medium.  The claim text is fully machine-readable from the `.odg`
files (see §4.5); the full hierarchy has already been extracted.
The main work is assigning good identifiers and verifying the nesting against
the figures.  Text labels may need minor rephrasing to fit LTAC's single-line
constraint (e.g., soft-hyphenated words like "authenti-cate" in the ODG labels).

### Stage 3 — Add evidence elements

**Goal**: Surface the evidence that currently lives only in prose into LTAC.

Steps:
1. For each section of `assurance-case.md` that mentions a specific code file,
   test result, document, or external URL as evidence, add an `Evidence` element
   to the corresponding LTAC claim.
2. Use the `(ref)` external-reference syntax to link evidence to URLs or file paths:
   ```
   - Evidence Ev-CSP: Content Security Policy enforced (app/controllers/application_controller.rb)
   ```
3. Use `<!-- caseproc element Ev-CSP -->` regions in `case.md` to position the
   detailed prose immediately after each evidence node's rendered view.
4. Run `caseproc --missing` to identify claims that still need support.

**Deliverable**: Each leaf claim is supported by one or more `Evidence` elements,
and the text evidence previously only in prose is now formally linked to the claim.

**Risk**: Medium.  Extracting evidence from prose requires human judgment about
which statements are actually evidence vs. context vs. argument.

### Stage 4 — Add Contexts and Assumptions

**Goal**: Capture scope constraints and accepted assumptions in LTAC.

Steps:
1. Add `Context` elements for scope information: operating environment, threat
   assumptions, ISO 12207 process scope, etc.
2. Add `Assumption` elements for claims accepted without further argument
   (e.g., "Heroku/AWS infrastructure is itself secure").
3. Add `Justification` elements for side-claims supporting strategies (e.g.,
   why a particular design principle is applicable here).

**Deliverable**: Richer LTAC with full Context/Assumption coverage.

**Risk**: Low.  These are additive; they don't restructure existing elements.

### Stage 5 — Polish and validation

Steps:
1. Run `caseproc --validate` and resolve all warnings.
2. Check that every `##`/`###` section heading still has a corresponding
   `<!-- caseproc element ... -->` region (or can be found via `package *`).
3. Review the generated Mermaid diagrams against the original `.odg` figures
   to catch structural errors.
4. Consider whether to split very large packages (e.g., `Implementation`)
   into sub-packages for readability.

---

## 4. Key Unknowns and Decisions Required

### 4.1 File location and naming

**Option A**: Keep `case.ltac` + `case.md` at the project root (`caseproc/`)
and point them at the `bp-docs/` content via relative paths.

**Option B**: Create `bp-docs/case.ltac` + `bp-docs/case.md` alongside the
existing assurance-case material.

Option B is simpler for Stage 1 (just add markers to the existing file)
and keeps the assurance case self-contained in `bp-docs/`.

### 4.2 Package granularity

The existing `.odg` files suggest 5–6 packages.  However, the `Implementation`
section alone spans ~1,000 lines and covers OWASP, misconfiguration, hardening,
and supply chain.  It may be better split into multiple packages (`OWASP`,
`Hardening`, `SupplyChain`, etc.) from the start.

### 4.3 Handling of the partial SACM conversion

The top-level SACM diagram (`assurance-case-toplevel-sacm.svg`) is already partially
converted.  Its claim IDs and structure should be the authoritative starting point
for the `case.ltac` top-level package rather than the CAE `assurance-case.odg`.

### 4.4 Treatment of the prose evidence

The document's text contains a very large amount of evidence (hundreds of specific
code references, test names, external links).  Two approaches:

**Option A (selective)**: Add LTAC `Evidence` elements only for the most
important evidence; leave secondary evidence only in the prose.

**Option B (comprehensive)**: Add LTAC `Evidence` elements for all evidence
mentioned, making the LTAC the authoritative evidence catalogue.

Option A is faster and lower risk; Option B gives a richer assurance case.
A hybrid (comprehensive for top-level claims, selective for leaf claims) is reasonable.

### 4.5 How to read .odg structure

The `.odg` files are ZIP archives containing ODF XML.
**All five key ODG files have been verified as directly machine-readable** —
no LibreOffice, no manual reading, no conversion step needed.

Two complementary extractions have been done and saved:

- **`bp-docs/odg-text-extracts.txt`** — all text labels from every shape (166 lines).
- **`bp-docs/odg-structure-extracts.txt`** — the full connector graph: every
  `child → parent` edge derived from LibreOffice connector objects (162 lines).

These files should be used as the primary source for Stage 2; re-extraction is
not needed unless the `.odg` files are edited.

**How text was extracted** (for reference / re-extraction):

```python
import zipfile, xml.etree.ElementTree as ET
TEXT = 'urn:oasis:names:tc:opendocument:xmlns:text:1.0'
with zipfile.ZipFile('assurance-case.odg') as z:
    root = ET.fromstring(z.read('content.xml'))
seen = set()
for el in root.iter('{%s}p' % TEXT):
    t = ''.join(el.itertext()).strip().replace('\u00ad', '')
    if t and t not in seen:
        seen.add(t)
        print(t)
```

**How graph structure was extracted** (for reference / re-extraction):

```python
DRAW = 'urn:oasis:names:tc:opendocument:xmlns:drawing:1.0'
shapes = {}
for el in root.iter():
    eid = el.get('{%s}id' % DRAW)
    if eid:
        label = get_text(el)   # as above
        if label: shapes[eid] = label
for el in root.iter('{%s}connector' % DRAW):
    s = el.get('{%s}start-shape' % DRAW)
    e = el.get('{%s}end-shape' % DRAW)
    if s and e and s != e and shapes.get(s) and shapes.get(e):
        print('%s  ->  %s' % (shapes[s], shapes[e]))
```

**Parentheses in description text** — LTAC treats `(text)` at the end of a description
line as an external reference.  Use square brackets `[text]` for any clarifying
annotations in description text, e.g. `[using bcrypt]`, `[2013 & 2017]`, `[XSS]`.

**Hyphen cleanup** — two kinds of spurious hyphens appear in the labels:

1. *Unicode soft hyphens* (U+00AD): removed mechanically by `.replace('\u00ad', '')`
   in the extraction above.
2. *ASCII line-break hyphens*: LibreOffice inserts regular `-` characters mid-word
   when text is too wide for a shape (e.g., `"pri-vacy"`, `"authenti-cate"`).
   These remain in the saved files and must be corrected manually when writing LTAC.
   A blanket regex over letter-hyphen-letter is **not** safe because many legitimate
   compound words also match (e.g., `"Non-public"`, `"Cross-site"`, `"Memory-safe"`).
   There are only a handful of wrapping artifacts; they are easy to spot and fix by hand.

The full claim/argument text extracted from each file is summarised below.

#### `assurance-case.odg` — top-level summary (CAE)

Top claim: *System is adequately secure against moderate threats*

- Security requirements identified and met by functionality
  - Confidentiality is maintained
    - Non-public data is kept confidential
      - Confidential data at rest protected
        - User passwords stored securely {using bcrypt}
        - Remember me token is secured
        - Email addresses are secured {encrypted, accessible only to admin & owner}
      - Data in motion encrypted with HTTPS
    - User privacy is maintained
    - Almost all data is not confidential
  - Integrity is maintained
    - Data modification requires authorization
    - Application modification requires authorization
  - Availability is maintained including limited DDoS resilience
    - CDN counters DDoS attacks on specific resources
    - Timeout limits maximum request time
    - Can return to operation quickly after DDoS ended
    - Logon disabled mode mitigates against some vulnerabilities
    - Data corruption and loss are mitigated by multiple backups
    - Cloud resources can be rapidly increased
  - Access control is in place
    - Users must identify and authenticate themselves
      - Local users must supply a password
      - Remote users are authenticated by a trusted remote service
    - Authorization to resources and actions is controlled
  - Assets & threat actors identified & addressed
- Security implemented by software life cycle processes *(→ next figure)*
  - Organized by life cycle processes

#### `assurance-case-lifecycle.odg` — lifecycle processes (CAE)

Top claim: *Security implemented by software life cycle processes*

- Security implemented by software life cycle **technical** processes
  - Security in requirements
  - Security in design
    - Simple design (economy of mechanism)
    - STRIDE threat model analyzed
    - Secure design principles applied (economy of mechanism, complete mediation,
      fail-safe defaults, open design, separation of privilege, least common mechanism,
      least privilege, psychological acceptability, limited attack surface,
      input validation with whitelists)
    - Availability through scalability
    - Memory-safe languages
  - Security in implementation *(→ next figure)*
  - Security in integration & verification
    - Automated testing >90% coverage (100% statement coverage)
    - Style checking tools
    - Source code weakness analyzer
    - Negative testing
    - FLOSS license verification
  - Security in transition & operation
    - Deployment provider
    - Detect: External monitoring + Internal logging/anomaly detection
    - Online checkers
    - Recovery plan incl. backups
  - Security in maintenance
    - Auto-detect vulnerabilities when publicly reported
    - Rapid update
- Security implemented by other life cycle processes *(→ other figure)*
- Certifications & controls
  - CII Best Practices Badge

#### `assurance-case-implementation.odg` — implementation (CAE)

Top claim: *Security in implementation*

- Strategy: Most vulnerabilities are due to common implementation errors or
  misconfigurations; countering them greatly reduces risk
  - All of the most common implementation vulnerability types (OWASP top 10) countered
    - All OWASP top 10 (2013 & 2017) countered: Injection, Broken Authentication,
      XSS, Insecure Direct Object References, Security Misconfiguration,
      Sensitive Data Exposure, Missing Access Control, CSRF,
      Known Vulnerabilities, Unvalidated Redirects, XXE (2017 A4),
      Insecure Deserialization (2017 A8), Insufficient Logging/Monitoring (2017 A10)
  - All common security-relevant misconfiguration errors countered
    - Entire most-relevant security guide (Rails Security Guide) applied
  - Reused software is secure
    - Reused software is reviewed before use
    - Reused software is authentic
    - Package managers used
    - Special analysis justifies exceptions
    - Known vulnerabilities detected
  - Hardening applied
    - HTTPS use enforced (including HSTS)
    - Outgoing HTTP headers hardened including restrictive CSP
    - Cookies limited
    - CSRF tokens hardened
    - Incoming rate limits enforced
    - Outgoing email rate limits enforced
    - Email addresses encrypted
    - Gravatar restricted

#### `assurance-case-verification.odg` — integration & verification (CAE)

**Note**: The connector-graph extraction reveals that almost all shapes in this
diagram are **isolated** — they are connected by freehand lines rather than
LibreOffice connector objects, so the structural edges are not captured in
`odg-structure-extracts.txt` for this file.  Only three edges are recorded:

- `File .circleci/config.yml`  →  `Successful verification required by CI before deployment`
- `Directory tests/`  →  `Negative tests failed as desired`
- `File .github/workflows/main.yml runs Brakeman`  →  `Source code analyzed for weaknesses & all issues resolved`

The hierarchy below is therefore reconstructed from the text labels plus the
prose in `assurance-case.md`, not from the connector graph:

Top claim: *Security in integration & verification*

- Strategy: Static & dynamic verifications performed and enforced on all
  integrations, reducing risk
  - Verification steps reduce risk
    - Static verifications are performed
      - Style checks pass
        - Evidence: Style checkers as pronto runners in Gemfile (eslint,
          rails_best_practices, rubocop); `.circleci/config.yml` runs pronto
      - Source code analyzed for weaknesses & all issues resolved
        - Evidence: `.github/workflows/main.yml` runs Brakeman
      - All reused components verified as FLOSS
        - Evidence: `.circleci/config.yml` runs license_finder; FOSSA check
    - Dynamic verifications are performed
      - Automated testing with excellent statement coverage (100%)
        - Evidence: `.circleci/config.yml`; codecov.io report
      - Negative tests failed as desired
  - Successful verification required by CI before deployment
    - Evidence: `.circleci/config.yml`

#### `assurance-case-other-lifecycle.odg` — other lifecycle processes (CAE)

**Note**: The connector graph is well-captured for this file, but
"Technical management processes" has no edge connecting it up to
"Security implemented by other life cycle processes" (it appears to be
connected by a freehand line rather than a connector object).

Top claim: *Security implemented by other life cycle processes*

- Agreement processes
  - Contracts with deployment and CDN provider
- Organizational project-enabling processes
  - Infrastructure management
    - Development & test environments protected from attack
    - CI automated test environment does not have protected data
  - Human resource management (people)
    - Key developers know how to develop secure software
- Technical management processes *(connector to top missing — freehand line)*
  - Project planning
  - Risk management
  - Configuration management
  - Quality assurance

---

**Stage 2 can now largely proceed directly**: the text and graph structure for
four of the five diagrams are fully extracted.  For the verification diagram,
the hierarchy must be inferred from text labels and the prose document rather
than the connector graph.  For the other-lifecycle diagram, one missing edge
needs to be added manually.

---

## 5. Existing Starting Point: `tests/fixtures/badgeapp-doc.ltac`

The file `tests/fixtures/badgeapp-doc.ltac` is already a reasonable Stage 1
skeleton and should be used as the starting point rather than created from scratch.
It demonstrates the correct approach:

```ltac
- Claim Security: The system is adequately secure against moderate threats
  - Strategy Processes: Security is argued by examining lifecycle processes
    - Claim Technical: Technical lifecycle processes implement security
      - Claim ^Requirements
      - Claim ^Design: The security design is documented and reviewed
      - Claim ^Implementation: The implementation process maintains security
      - Claim ^Verification: Integration & verification confirm security
      - Claim ^Deployment: Deployment maintains security
      - Claim ^Maintenance: The maintenance process maintains security
    - Claim ^NonTechnical: Non-technical lifecycle processes implement security
    - Claim ^Controls: Certifications & controls provide confidence in operating results

- Claim Requirements: Security requirements are identified and met
  - Evidence ReqSpec: Requirements specification (docs/requirements.md)
  - Evidence TestCoverage: Test coverage report (reports/coverage.html)
  - Context ReqScope: Applies to all user-facing features

- Claim Design: The security design is documented and reviewed
  - Evidence DesignDoc: Security architecture document (docs/security-arch.pdf)
  - Evidence ThreatModel: Threat model (docs/threat-model.md)
```

**What it gets right:**
- Multi-package structure with a summary package at the top.
- `Strategy Processes` decomposes by lifecycle — exactly matching the real document's
  "defense-in-breadth" framing.
- Cross-package `^` citations connect the top-level summary to sub-packages.
- Identifier naming is meaningful (not GSN-style `G1`/`G2`).
- Shows the right mix of Claim, Strategy, Evidence, and Context elements.

**Gaps to fill in Stage 2+:**
- Only 3 of the 8+ cited packages are defined (`Security`, `Requirements`, `Design`).
  `Implementation`, `Verification`, `Deployment`, `Maintenance`, `NonTechnical`, and
  `Controls` are referenced with `^` but not yet defined.
- Evidence references are illustrative placeholders; real paths differ
  (e.g., `docs/requirements.md` → `bp-docs/requirements.md`).
- Many levels of sub-claim detail are absent (added in Stages 2–3).

---

## 6. Recommended First Step

Begin with **Stage 1, Option B** (files in `bp-docs/`):

1. Copy `tests/fixtures/badgeapp-doc.ltac` to `bp-docs/case.ltac` as the starting
   skeleton.  Add stub packages for each of the currently-missing `^`-cited packages
   (one top-level `Claim` each, marked `{needsSupport}`) so that caseproc's
   reachability check passes.
2. Copy `bp-docs/assurance-case.md` to `bp-docs/case.md`, replacing the block of
   four `![Assurance case ...]` figure lines (around lines 62–65 of that file) with:
   ```markdown
   <!-- caseproc package * -->
   <!-- end caseproc -->
   ```
3. Run `caseproc` in `bp-docs/` to confirm the toolchain works with this document.
4. Iterate on Stage 2 one package at a time, validating after each.

This first step is reversible, requires no structural decisions about evidence,
and immediately replaces the static `.odg`-generated images with live caseproc
diagrams that stay in sync with the LTAC.
