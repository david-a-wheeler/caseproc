# Report 6: Convert Best Practices Assurance Case

I would like to try to convert the best practices badge assurance case
to use the new caseproc system. We'll eventually create
case.ltac and case.md files.

However, since this kind of conversion has never been done before,
I want to first do some research on our existing materials so we can
have a good conversion.

Produce a report in `docs/conversion-report.md` that summarizes
key information describing this assurance case, and propose approaches
for converting it into caseproc form.

We want to have a good understanding of the LTAC format and markdown
format required. So first review these documents:

- docs/ltac-extended.txt
- docs/tutorial.md

If you need more information about the caseproc tool,
consult `docs/reference.md` or other materials in `docs/` as necessary.

Then review the assurance case materials in directory `bp-docs/`
starting with `bp-docs/assurance-case.md`.
This is an assurance case that is written as a traditional markdown document.
It references several CAE structures, with a starting attempt in SACM.
Much of the material we'll need to convert to LTAC is recorded as
graphics in the files `bp-docs/*.odg`.
I suspect each graph will convert into 1 or more packages.

We'll want to do this in stages, to prevent data loss and increase
the likelihood of correctness.
I suspect I'll want a stage
where much is in LTAC, but we *only* change the headers to use caseproc
element regions and add a caseproc `<!-- caseproc package * -->`
where the current list of figures are. That said, I think there are
many options and unknowns.

So report what you've learned, and propose the start of a plan to do
the conversion (including options). Thanks!
