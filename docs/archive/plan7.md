# Plan 7

In LTAC, I believe parenthesis should *only* define a reference if they
occur at the *end* of a line. Parentheses should otherwise, after
the "ID:", be accepted as part of the text.
This make the parentheses syntax *slightly* less
annoying (I would like to use parentheses more often).

Please see file ltac-extended.txt to confirm (or not) this understanding.

Unfortunately, that isn't what happens.

Given file `test.ltac`:

~~~~
- Claim Foo
  - Claim (this is) fine
~~~~

Running this:

~~~~
../caseproc --select 'ltac *' --ltac test.ltac 
~~~~

Produces this error:

~~~~
caseproc: error: line 2: unrecognized syntax: '  - Claim (this is) fine'
### Package Foo
- [Claim Foo](#claim-foo)
~~~~

We should modify caseproc so a pair of parentheses *not* at the end of the
line isn't considered part of a reference. My example should create
statement text `(this is) fine`.

I think we need to modify `_LTAC_LINE_RE` to implement this.
