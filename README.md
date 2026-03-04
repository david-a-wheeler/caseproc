# caseproc README

`caseproc` is a simple open source software tool
that makes it *easy* and *efficient*
to create and maintain a moderately-sized assurance case.
It's a simple Python3 script that processes our
extended version of the Lightweight Text Assurance Case (LTAC) format,
along with markdown or HTML documentation,
to generate useful assurance case documentation.

An assurance case is "a body of evidence organized into an argument demonstrating that some claim about a system holds (i.e., is assured). An assurance case is needed when it is important to show that a system exhibits some complex
property, such as safety, security, privacy, or reliability."
([NIST Special Publication 800-53A Revision 5](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-53Ar5.pdf)).

## Background

There are many notations for expressing and maintaining assurance cases,
including SACM, GSN, and CAE.
Large assurance cases are often maintained using specialized tools that
manage databases of such information.
These tools allow people to edit
diagrams that flexibly present the information graphically.
For large assurance cases these tools are quite helpful!
However, it's hard to argue
for the use of these sophisticated tools for a smaller assurance case.

The obvious alternative is to write an assurance as a traditional document.
However, traditional documents don't provide any support for the
structure between the parts of an assurance case.
As a result, maintaining them requires a lot of extra work, and they
often go slowly out of date. They often don't provide any graphics to
show the overview, or they do so only at a very high level.

## Our approach

This tool, `caseproc`, takes a different approach:

* As input, it reads a simple text file written in our
  extended version of the Lightweight Text Assurance Case (LTAC) format.
  This lets you easily express a hierarchy of structure, and will immediately
  detect a number of invalid constructs.
* As output, it takes a set of 1+ documents (markdown or HTML)
  and inserting graphics and text at specific insertion points.
  Note that it *automatically* generates graphical notation in SACM or
  GSN notation - you don't need to fiddle with the graphics at all.

Currently it can generate SACM notation in mermaid format.
We eventually hope to support other notations, specifically GSN and CAE.
It can also generate a markdown indented bullet list that looks like LTAC
format but adds hyperlinks, making it easy to go from a high-level
summary to specific details and back.

Perhaps most usefully, its `-i` (in place) option
allows you to update the markdown/HTML files in place.
So you can simply run the process with a sequence of markdown filenames,
and it will update the documents directly.

## Pros and Cons

The big pro of this approach is that it takes very little time to
get started, get graphical representations, and generate information.
It's also fairly easy to edit material.
The key outline of the assurance case is stored in the LTAC file.
The details (e.g., the "contents" in SACM terminology) is always
kept in one or more markdown or HTML file, which is updated by this program.
Everything is done in easily-edited files.
Since we *do* have some basic information on the element types
in the assurance case, we can report (and complain) about problems in it.
We can also complain about problems such as an element with no supporting
information.
In short, this makes it easy to notice and fix problems in a way
that pure document does not.

The big con of this approach is that to make it work, we are intentionally
imposing various limits:

* The hierarchical representation of LTAC forces a hierarchy that GSN and SACM
  don't natively require. Instead, we require that an assurance case
  be grouped into multiple packages (modules),
  each one have a single top claim, and that they be hierarchical from there.
  We name the package after that top claim.
  We also require that any claim only be defined in one package.
  However, a claim may be *referenced* in many packages, and "Links" allow
  references to an element already in use.
  So this restriction isn't a serious problem in practice.
* We generate graphics automatically, and we currently
  use `mermaid` because it's
  directly support by GitHub's built-in markdown processor.
  Mermaid is quite limited in what it can do. This isn't as bad if you
  limit your packages to smaller numbers of elements.
* This is not a database, it's a way to make it easier to manage documents.
  If you want a database, this isn't it.

## Other information

The specification of LTAC we implement is in file
[docs/ltac-extended.txt](docs/ltac-extended.txt).
