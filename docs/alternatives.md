# Alternatives to caseproc

`caseproc` occupies a largely unique niche:
plain text LTAC input, in-place markdown/HTML output,
auto-generated Mermaid SACM/GSN diagrams, and no external dependencies.
It was formerly named `ltacproc`.

The tools below are alternative tools for managing assurance cases
according to CoPilot.

TODO: Verify these.

## Text-based tools

**[GSN Editor for VS Code](https://marketplace.visualstudio.com/items?itemName=vu-isis.gsn-assurance)**
([source](https://github.com/vu-isis/gsn-domain), MIT license):
An open-source VS Code extension developed by Vanderbilt ISIS that provides
a text DSL (`.gsn` files) for Goal Structuring Notation assurance cases,
combined with a live graphical editor that renders the model as a
directed acyclic graph.
Inputs are textual `.gsn` files whose syntax covers goals, strategies,
contexts, assumptions, and solutions; outputs are synchronized graphical
diagrams inside VS Code.
It supports multi-file models with namespaces, syntax highlighting,
grammar validation, and code completion backed by a language server.
A CLI tool (`json2gsn`) can convert JSON representations to `.gsn` files.
Requires Java 8+ and VS Code; it does not update existing documents in-place.

## More heavyweight open-source tools

**[D-Case Editor](https://github.com/d-case/d-case_editor)**
([project site](http://www.dcase.jp/p/eeditor.html), Eclipse Public License v1.0):
An Eclipse plug-in developed in Japan for creating and managing structured
assurance cases using Goal Structuring Notation.
Users interact with a graphical editor to build GSN diagrams; cases can
be exported in standard formats such as OMG ARM for use in other tools.
Features include a GSN pattern library for reusable argument templates,
type checking, consistency checking, and integration with system monitoring
architectures for live assurance updates.
Being Eclipse GMF-based, it benefits from a rich extensibility ecosystem
but requires a full Eclipse installation.

**[AdvoCATE](https://assured-autonomy.org/tools/advocate)**
([NASA user guide](https://ntrs.nasa.gov/api/citations/20220009664/downloads/AdvoCATE%20User%20Guide_1.4.pdf),
open access for non-commercial/research/government use):
The Assurance Case Automation Toolset, developed at NASA Ames Research Center
and widely referenced by the FAA for aviation safety certification.
It supports both manual and semi-automated assembly of assurance cases,
with full Goal Structuring Notation (GSN Community Standard) and
OMG Argumentation Metamodel (ARM) compliance.
Inputs include structured argument descriptions, reusable argument patterns,
formal-methods outputs, and hazard/risk analyses (PHA, FHA, bow-tie diagrams).
Outputs include composed assurance case modules with traceability links to
requirements, hazards, and evidence artifacts, plus reports and metrics for
quantitative assessment of case quality.
It supports modularization, hierarchical abstraction, and integration
with safety analyses, making it one of the most feature-rich tools available,
though also one of the most complex to learn.
See
[AdvoCATE: An Assurance Case Automation Toolset](https://www.faa.gov/about/office_org/headquarters_offices/ang/redac/redac-sas-201503-advocate.pdf); its abstract says, "We present AdvoCATE, an Assurance Case Automation ToolsEt, to
support the automated construction and assessment of safety cases. In
addition to manual creation and editing, it has a growing suite of
automated features.  In this paper, we highlight its capabilities
for (i) inclusion of specific metadata, (ii) translation to and from
various formats, including those of other widely used safety case tools,
(iii) composition, with auto-generated safety case fragments, and (iv)
computation of safety case metrics which, we believe, will provide a
transparent, quantitative basis for assessment of the state of a safety
case as it evolves. The tool primarily supports the Goal Structuring
Notation (GSN), is compliant with the GSN Community Standard Version 1,
and the Object Modeling Group Argumentation Metamodel (OMG ARM)."

**[OntoGSN](https://fortiss.github.io/OntoGSN/)**
([GitHub](https://github.com/Tomas-Bueno-Momcilovic/OntoGSN),
ontology: CC-BY-4.0, software: MIT):
An ontology and middleware toolkit developed by fortiss for semantic,
graph-based management of GSN assurance cases.
Cases are expressed as OWL 2 ontologies (built with Stanford Protégé),
with all GSN elements mapped from the GSN Community Standard v3.
This enables machine-readable, logic-based quality verification via SWRL
rules, OWL axioms, and reasoners such as Pellet, as well as SPARQL queries
for automated CRUD operations and consistency checks.
It is designed for dynamic, continuously updated assurance cases — for
example, linking runtime data from autonomous vehicle or AI systems directly
into the argument structure.
A higher learning curve than plain-text tools, but offers unique capabilities
for formal reasoning and LLM/GraphRAG integration.

**[CertWare](https://nasa.github.io/CertWare/)**
([GitHub](https://github.com/nasa/CertWare)
core: Apache 2.0 / NASA Open Source Agreement;
Bayesian engine: UCLA non-commercial research license):
An open-source Eclipse-based safety case workbench developed and sponsored
by NASA, targeting aerospace and other high-integrity engineering domains.
CertWare supports multiple argumentation standards: GSN, CAE, and the
OMG Argumentation Metamodel (ARM), with both graphical and structured
tree editors for building and viewing cases.
Inputs are cases built interactively in Eclipse or imported from Word/XML;
outputs include GSN/CAE diagrams, Microsoft Project exports (MSPDI),
and validation reports.
Notable features include a Bayesian network analysis engine for reasoning
about uncertain evidence, change-tracking, project metrics, validation
and semi-formal proof checklists, and EGit-based version control for
multi-user collaboration.
([NASA open-source tools for safety cases](https://c3.ndc.nasa.gov/dashlink/static/media/project/Flyer.pdf))

**[ACedit](https://github.com/arapost/acedit)**
(open source, Eclipse-based):
A lightweight open-source Eclipse plug-in for creating and editing
assurance cases in GSN and OMG ARM notation, originally hosted on
Google Code and now mirrored on GitHub.
It provides graphical editing of GSN elements (goals, strategies,
solutions, contexts, assumptions), evidence attachment, and
consistency/type checking, integrated into the Eclipse ecosystem.
The project is relatively old and appears to have had limited
maintenance in recent years, making it primarily of historical or
research interest compared to more actively maintained alternatives.

**[Resolute](http://loonwerks.com/Resolute-Updates/)**
([GitHub/Loonwerks](https://github.com/loonwerks/formal-methods-workbench-updates),
BSD license):
An assurance case language and OSATE plug-in developed at
Collins Aerospace (Loonwerks) that generates and evaluates
assurance cases directly linked to AADL (Architecture Analysis and
Design Language) architectural models.
Users define *claim functions* in a Resolute annex inside AADL packages,
forming hierarchical claims whose truth depends on sub-claims or
computational predicates evaluated against the model.
Resolute can incorporate results from other formal analysis tools
(e.g., the AGREE contract-based model checker) as evidence,
and its OSATE view provides an "Assurance Case" result tree
with traceability from architecture to verified claims.
Changes to the architecture automatically surface unsatisfied claims.
Particularly relevant for aviation, automotive, and defense certification.
([Paper: "Resolute: An Assurance Case Language for Architecture Models"](https://arxiv.org/pdf/1409.4629))

**[safeTbox](https://safetbox.de/)**
([features](https://safetbox.de/features/),
[Fraunhofer IESE](https://www.iese.fraunhofer.de/en/services/safety-engineering/safetbox.html),
free for non-commercial use; commercial license via Fraunhofer IESE):
A model-based safety engineering framework developed by Fraunhofer IESE,
implemented as an extension to Sparx Systems Enterprise Architect (EA),
so a valid EA v13+ license is also required.
It provides an integrated environment for architecture modeling (SysML 1.3/1.4),
hazard and risk assessment (HAZOP templates, ISO 26262),
fault tree analysis (Component Fault Trees with quantitative analysis),
STPA (Systems Theoretic Process Analysis) for safety and security,
and GSN-based assurance case authoring with modular argument support.
All artifacts are linked for full traceability across the system lifecycle.
Widely used in automotive (ISO 26262, ISO 21448/SOTIF, ISO 21434),
aerospace, and industrial safety domains.
([Blog: GSN with safeTbox](https://www.iese.fraunhofer.de/blog/gsn-with-safetbox-tool-for-safety-argumentation/))

## Commercial / database-style tools

These tools use a proprietary database or web backend and are not
text-file-based workflows.

**[Astah System Safety](https://astah.net/products/astah-system-safety/gsn-goal-structuring-notation/)**
(commercial — approx. $550/year per user; academic and trial licenses available):
A commercial modeling tool from Change Vision (Japan) specifically designed
for GSN assurance cases and model-based safety engineering.
Input is a proprietary project file; the tool provides a graphical GSN
diagram editor with auto-layout, drag-and-drop goal creation,
and modular assurance case composition using public indicators and
SupportedBy/InContextOf relationships, compliant with GSN Community Standard v1.0
and OMG SACM for import/export.
It integrates tightly with SysML — requirements can be converted to GSN goals
with synchronized traceability — and a script editor supports custom automation
such as checking evidence links or counting goals.
Outputs include diagram images, exportable model files, and synchronized
documentation. Team collaboration is supported via model comparison and merge.
Available on Windows, macOS (including Apple Silicon), and Linux.
([Software Advice review](https://www.softwareadvice.com/diagram/astah-system-safety-profile/))

**[Adelard ASCE](https://www.adelard.com/asce/)**
([datasheet](https://www.adelard.com/media/gqcbmjxh/mk138v11_asce_51_datasheet.pdf),
commercial — node-locked or floating licenses; evaluation licenses available):
The Assurance and Safety Case Environment from Adelard is a widely adopted
commercial tool used in defense, nuclear, rail, healthcare, and other
regulated industries.
Users build assurance cases graphically using GSN or Claims-Argument-Evidence
(CAE) notation, with dynamic traceability links to external evidence documents
that trigger notifications when referenced material changes.
Outputs include high-quality reports in Word, PDF, or interactive HTML
suitable for regulatory submissions and audits.
Additional features include bird's-eye view navigation, impact analysis,
modular GSN support, an Assurance 2.0 framework for managing defeaters and
counter-evidence, and optional integration with IBM Rational DOORS.

**[Argevide PREMIS](https://www.argevide.com/assurance-case/)**
([resources](https://www.argevide.com/resources/),
free for one project; contact Argevide for commercial/org pricing):
A web-based, containerized (cloud, Kubernetes, VM, or dedicated server)
assurance case management platform used across automotive, aerospace,
process industry, cybersecurity, and medical-device domains.
PREMIS is compliant with GSN Community Standard v3, OMG SACM v2.3,
and ISO/IEC 15026-2:2022, and can import LTAC-format text files,
converting them into structured GSN diagrams.
Core features include real-time online collaboration, modular assurance
cases with reusable templates, role-based access control, a full audit log
with baselines, integrated verification steps, continuous assurance via
live data feeds, and a REST API for external integration.

## Related tools

The paper [Explainable Compliance Detection with Multi-Hop Natural Language Inference on Assurance Case Structure](https://arxiv.org/pdf/2506.08713v1)
discusses "EXPLAIN". Per its abstract:
"Ensuring complex systems meet regulations typically requires checking
the validity of assurance cases through a claim-argument-evidence
framework. Some challenges in this process include the complicated
nature of legal and technical texts, the need for model explanations, and
limited access to assurance case data. We propose a compliance detection
approach based on Natural Language Inference (NLI): EXplainable CompLiance
detection with Argumentative Inference of Multihop reasoning (EXCLAIM). We
formulate the claim-argument-evidence structure of an assurance case as a
multi-hop inference for explainable and traceable compliance detection. We
address the limited number of assurance cases by generating them using
large language models (LLMs). We introduce metrics that measure the
coverage and structural consistency. We demonstrate the effectiveness
of the generated assurance case from GDPR requirements in a multi-hop
inference task as a case study. Our results highlight the potential of
NLI-based approaches in automating the regulatory compliance process."

## Not separate assurance case tools

These are **not** assurance case tools in their own right:

- **SCE (Adelard Safety Case Environment)** — the earlier name for Adelard ASCE
  (see above); they are the same product line.
- **NOR-STA** — an earlier product from the company now known as Argevide;
  it evolved into PREMIS (see above).
- **AGSN** — not a distinct standalone tool; searches conflate it with the
  D-Case Editor project.
- **AutoFOCUS 3** — a fortiss open-source model-based systems engineering tool
  ([fortiss.org](https://www.fortiss.org/en/results/software/autofocus-3));
  it is primarily for system architecture modeling and does not provide
  native assurance case authoring.
