# caseproc Tutorial

This is the tutorial for `caseproc`.
`caseproc` is a simple open source software tool
that makes it *easy* and *efficient*
to create and maintain a small or moderately-sized assurance case,
e.g., for justifying why a system is secure against attack.
It's designed to be easy to use for humans *and* AI.

## What's an assurance case?

An assurance case is "a body of evidence organized into an argument demonstrating that some claim about a system holds (i.e., is assured). An assurance case is needed when it is important to show that a system exhibits some complex
property, such as safety, security, privacy, or reliability."
([NIST Special Publication 800-53A Revision 5](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-53Ar5.pdf)).

Assurance cases are in theory straightforward.
Typically you have a high-level claim that you repeatedly break down into
smaller claims that together demonstrate that the claim holds.
The problem is that as they get large, they can be painful to follow
or maintain if you just maintain a document.

## TL;DR: Quick start using caseproc

Create an empty directory (e.g., `mkdir demo; cd demo`).
Now create a starter sample with the `--start` option:

~~~~sh
caseproc --start
~~~~

This creates a `case.ltac` and a `case.md` file.

The `case.ltac` file is a simple file that shows basic structure
of the assurance case, with repeatedly indented elements,
in [Extended LTAC format specification](ltac-extended.txt) format.

Here's what the file `case.ltac' might look like:

~~~~ltac
- Claim Secure: The system is secure
  - Claim G2: G2 is true {needssupport}
  - Claim G3: G3 is true {needssupport}
~~~~

Every non-blank line expresses an `element` of the case by starting with indentation (2 spaces per level) and `-`. There are several types of elements such as `Claim`, `Strategy`, `Assumption`, and `Evidence`. A `Claim` is a true-or-false claim. The element type is usually followed by its ID, which is usually short and *may* have spaces.

Strictly speaking, the ID is syntactically optional. If you don't specify an ID, the text is used as an ID (keeping spaces but removing a few characters like parentheses and curly braces). That said, we strongly encourage assigning an ID to each element; assigning IDs makes things easier.

Every element in an assurance case has an ID (either stated directly or inferred from the text after the colon). Each ID is required to be globally unique.

This type and optional ID is followed by colon, space, and the textual statement(in this case, the true/false statement of the claim).

You can insert a blank line and start another "package" of elements,
starting again from the top (0 indents). You can cite an element, instead of
defining it, by using "^" in front of its ID.
You can cite an element as many times as you want, but you can only define it
(use with with a leading "^") once in assurance case.
Citations make it easy to break down a complicated assurance case into
a number of smaller packages.

The file `case.md` contains markdown with all the details.
It's a document you can edit.
However, every region between these two markers will be updated
by `caseproc`, so don't edit between any of them:

~~~~markdown
<!-- caseproc ... -->
<!-- end caseproc -->
~~~~

The sample starter creates the region `<!-- caseproc package * -->`;
this will insert headings for every package, and for every package it
will generate graphics and various useful hyperlinks.

Whenever you run `caseproc` without any arguments, the tool will check
to see if `case.ltac` is valid (and tell you if it isn't), and will
update `case.md` (or whatever your documents are).
This updating includes creating diagrams, hyperlinks, and so on.

The `caseproc` tool has various options that can be used to
ease maintenance of the assurance case. Normally the tool never updates
the LTAC file, only the documentation file(s), but some options
*do* change the LTAC file. This includes:

* `--update`: update the LTAC file to synchronize citation
   statements with their declarations
* `--rename OLD NEW`: rename identifier OLD to NEW in LTAC and document files.
  If an identifier includes a space, be sure to surround the identifier
  with "..." or '...' when invoking this command from the shell
* `--restate LABEL STATEMENT`: update the statement for LABEL in LTAC
  and document files.
  If the identifier or statement includes a space, be sure to surround
  them with "..." or '...' when invoking this command from the shell
* `--missing`: re-render document files and insert element selectors
  for missing elements; also flags leaf elements with needsSupport in the LTAC
