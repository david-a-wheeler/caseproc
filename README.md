# verocase README

`verocase` is an open source software (OSS) tool
that makes it *easy* and *efficient*
to create and maintain an assurance case, for both humans and AI.
The name verocase is derived from the Latin *vero*
(meaning "in truth" or "truly") and *case*,
(representing the tool's purpose to manage an assurance case).
See [background](#background) for more information on what an assurance case
is and various approaches for managing one.

The `verocase` tool takes a very different approach from other
tools for managing an assurance case. This tool
reads a file written in our extended version of the
[Lightweight Text Assurance Case (LTAC) format](docs/ltac-extended.txt),
which provides a basic outline of *why* some claim is true,
and then updates all related markdown or HTML documentation.
The tool can automatically generate graphics
for both Structured Assurance Case Metamodel (SACM) and
Goal Structuring Notation (GSN). It can also generate many hyperlinks
to make navigation easy.

Both humans and AI should find it *very* easy to create and edit an
assurance case this way.
The inputs are simple text files, making them easy to read and easy
to modify. AI systems *really* like recursively indented information
like LTAC (Python, YAML, and many other formats already do this) and
they know how to handle Markdown (they've been trained on vast amounts of it).

Processing is lightning-fast, too. In one real-world assurance case
with over 200 elements and 370Kib of documentation, processing
takes less than 0.2 seconds.

The [tutorial](docs/tutorial.md) explains how to use the tool.
It's *really* easy to get started.
The tool has lots of capabilities, but using them is entirely optional.
The [reference manual](docs/reference.md) explains the tool capabilities
in detail. We take steps to make the tool trustworthy through
our extensive test suite, linting, and static type analysis.

## Background

An assurance case is "a body of evidence organized into an argument
demonstrating that some claim about a system holds (i.e., is assured). An
assurance case is needed when it is important to show that a system
exhibits some complex property, such as safety, security, privacy,
or reliability."
([NIST Special Publication 800-53A Revision 5](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-53Ar5.pdf)).

In *principle* maintaining an assurance case is easy.
You start with the claim you're trying to make, and repeatedly subdivide
that claim using subclaims, arguments, and so on.
In the end you have a structure with many claims, arguments, assumptions,
and evidence, until finally you show that all the bottom
"leaf" claims are true.
However, problems can show up when you try to do this at scale.

This tool, `verocase`,
represents a completely *different* approach for maintaining an
assurance case. First, we'll explain common approaches, and then
we'll explain how verocase is different.

### Traditional document

One approach for maintaining an assurance case
is to maintain it entirely as a traditional document.
That's possible, and traditional document editing tools make it easy to
edit documents.
I've done this for over a decade on one project using LibreOffice.

However, this approach doesn't provide *any* support for the
structure of an assurance case.
Maintaining an assurance case
this way requires a lot of extra work to keep the different parts consistent.
It's too easy to make mistakes, leading to inconsistencies,
and the results often go slowly out of date.

What's more, ordinary document processing tools
don't provide many helpful graphics to show the overview of the assurance case.
There are several widely-used graphical notations for easily
expressing and maintaining assurance cases, including
the Object Management Group's
[Structured Assurance Case Metamodel (SACM)](https://www.omg.org/spec/SACM),
[Goal Structuring Notation (GSN)](https://scsc.uk/gsn-standard), and
[Claims Arguments Evidence (CAE)](https://claimsargumentsevidence.org/notations/claims-arguments-evidence-cae/).
Using widely-understood graphical notation makes the assurance case
easier to understand.
However, it's burdensome to create and maintain these graphics by hand.
I did this with LibreOffice, which has some nice tools for maintaining
graphics, but as a generalized tool it involved a lot of extra work.

An AI can help, but it's no miracle.
It's error-prone for *humans* to maintain an assurance case in
a document-only approach.
AI can make exactly the same kind of mistakes, for the same reasons.
Once assurance cases grow from being tiny, it's really helpful to have some
kind of automated support.

### Graphics editing and database tools

Large assurance cases are often maintained using specialized tools that
manage a database containing the assurance case structure and more
detailed information.
Examples include
[Adalard ASCE](https://www.adelard.com/asce/) and
[Argevide PREMIS](https://www.argevide.com/assurance-case/).
These specialized tools allow people to directly edit
diagrams that flexibly present the information graphically.
Since they *know* about at least one common assurance case notation, they
are designed to make it easy to create the graphics and enter the data.

For large assurance cases where maximum flexibility is critical,
these tools can be quite helpful.
They're especially helpful for users who aren't comfortable editing a text file,
and would strongly prefer to enter and manipulate data through a GUI.
If this is the kind of tool you want,
by all means, check them out!

However, these sophisticated tools seem excessive for some assurance cases.
These tools require installation, learning to use them, and committing to
storing all data in a database that can only be managed by a complex tool.
I was looking for a simpler alternative where it would be much
faster to edit the assurance case and where I could manage the result with git.

### Our approach as an alternative

As noted above, this tool `verocase` takes a completely different approach:

* As input, it reads a simple text file (default file `case.ltac`
  in `./` or `docs/`). This file is written in our
  extended version of the Lightweight Text Assurance Case (LTAC) format.
  This simple format makes it
  easy to express a simple hierarchy of structure and high-level statements.
  The `verocase`
  tool will identify and report various kinds of invalid constructs
  (e.g., citations of undefined elements, invalid types, logical circularity,
  unreachable elements, and so on).
* As output, it updates a set of 1+ documents (in markdown or HTML),
  including fixing headers and inserting/updating graphics
  (default file `case.[md,html]` in `./` or `docs/`).
  Note that it *automatically* generates graphical notation in SACM or
  GSN notation. You don't need to fiddle with the graphics at all.
  It also automatically generates many hypertext links, making it
  easy to navigate the assurance case.
  The expectation is that humans and AIs would edit these "document files"
  to provide all the details (aka SACM "content").

In short: just run `verocase` and the document files will be updated
based on the input LTAC file.

The tool can generate SACM, GSN, and CAE notation in mermaid format.
It can also generate a markdown indented bullet list that looks like LTAC
format but adds hyperlinks, making it easy to go from a high-level
summary to specific details and back.
The tool can also insert various cross-references and update heading names
as appropriate.

The result is *much* easier to integrate into version control systems like git,
since all information is kept in simple text files.
This simplifies review and collaborative development.
Both AI and humans find this information really easy to follow.
AI systems love markdown and HTML, and they
also know how to handle indented structures like LTAC since they've seen
them elsewhere (e.g., in YAML and Python).
It's remarkably easy to edit, too - just use any text editing tool.

## Handling evolution

Assurance cases evolve.
If you *purely* edit an assurance case
in a document various errors can creep in, the diagrams and document
headings can easily go out of sync,
and there's no hint that there's a problem.
This tool is designed to easily handle assurance case evolution
better than a simple document can.

This tool does a number of validation checks;
see `--help-validations` for the full list.
If it passes basic validation,
the tool by default will automatically update the document files to match
the LTAC input, e.g., it updates the graphics and the headings.

Database-based tools can make it easy to make specific changes "everywhere".
However, database-based tools are complex and require the use of a
specialized tool for almost all assurance case tasks.
Our goal is to get many of those benefits using a completely different and
simpler approach.

We achieve similar capabilities using a few simple options.
Normally the tool will only *read* the LTAC file, not modify it.
However, a few options will *update* the LTAC file:

* `--update` option: updates the LTAC file so that all elements that cite an
  element will have their statements updated to match the definition.
* `--rename OLD NEW` let you rename IDs in the LTAC and document files.
* `--restate LABEL STATEMENT` lets you change the statement of a given label
  in the LTAC and document files.
* `--detach ID` detaches ID from its current package, and makes it the
  head of its own package.

These options give us many of the advantages of database-based approaches
(you can do one operation to change
certain values "everywhere"), while providing better transparency,
greater simplicity, and easier integration with AI and version control tools.

## Pros and Cons

The big pro of this approach is that it takes very little time to
get started, get graphical representations, and generate information.
It's also fairly easy to edit material.

The key outline of the assurance case is stored in the LTAC file.
The details (e.g., the "contents" in SACM terminology) is always
kept in one or more markdown or HTML files, which are
updated by this program.
Everything is done in easily-edited files, not in a database that
requires a special tool to maintain.
Since we *do* have some basic information on the element types
in the assurance case, we can report (and complain) about problems in it.
We can also complain about problems such as an element with no supporting
information.
In short, this approach makes it easy to notice and fix problems in a way
that a pure document approach does not.

The big con of this approach is that to make it work, we are intentionally
imposing various limits:

* We *require* that the assurance case be organized as a set of packages,
  where each package is a strict tree hierarchy.
  This restriction is required by our extended LTAC input form.
  This restriction is allowed but not strictly required by widely-used
  assurance case notations like GSN, SACM, and CAE.
  This is key to our approach; this restriction greatly simplifies the
  expression the assurance case, as a package can now be represented as
  indented information.
  Each package must have a single top claim or justification, as
  we name the package after that top element.
  We believe restriction is not a problem in practice, because
  a claim or justification may be *referenced* in any package,
  and "Links" allow references to an element already in use in a package.
* Our inputs are *text* not graphics. I find that entering data as simple
  text is far more efficient. If you want to enter data as graphics,
  this is the wrong tool for you.
* We generate graphics automatically. In addition, we currently
  use `mermaid` because it's
  directly support by GitHub's built-in markdown processor.
  Mermaid is limited in what it can do.
  For example, mermaid will sometimes let lines overlap, and you simply
  have to live with its less-than-fancy rendering.
  In practice, mermaid's limits aren't a serious problem if
  your packages don't have too many elements.
  You can have as many packages as you want, so we suggest
  limiting the size of each package (the `--detach` operation will easily
  break up a package for you). Smaller packages are
  easier for humans to follow, too.
* This is not a database, it's a way to make it easier to manage documents.
  If you want a database, this tool isn't it.

This is primarily focused on small to medium-sized assurance cases.
That's not because it has a size limit; it should be able to handle
millions of elements without an issue.
However, it requires that the assurance case be organized as a set of
trees (aka a "forest"), and that may be too restrictive for some.

## Other information

We love contributions! See [CONTRIBUTING.md](./CONTRIBUTING.md).

The specification of extended LTAC that we implement is in file
[docs/ltac-extended.txt](docs/ltac-extended.txt).
