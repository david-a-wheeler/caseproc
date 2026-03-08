# Plan 9

No, this isn't from outer space :-).

## Reorder reference and options

When I extended LTAC, I added options after the reference, this way:

~~~~
Element         = Indent "-" WS NodeType [WS Identifier] ":" WS Text [WS Reference] [WS Options] Newline
~~~~

However, I believe `[WS Reference]` and `[WS Options]` should
have their order *swapped*. That way, a system that can only read *old*
LTAC won't reject the LTAC if it's for one package - the options will
instead be considered part of the statement. That's better, because then
the information isn't lost, it's associated with the element, and the
file *can* be read in such a circumstance.

Modify `docs/ltac-extended.md` (I think you just need to swap
them in that one line). Implement this change in the `caseproc` tool,
our tests, and bp-docs/case.ltac. When implementing this change in our
tests and case.ltac, do a grep first - I suspect doing both a reference and
options is extremely rare. There may not even be a test of this; if there
isn't, add one where we have both an option and a reference.

## Warn on dubious reference

It's really easy to add a parenthetical at the end of a statement
and have it incorrectly interpreted as a reference.

Let's add a new config option, `warn_dubious_reference`, default true.
If true, we emit a warning every time we read a reference from an LTAC
file that is non-empty but "dubious".

Whether or not a reference is "dubious" is a heuristic.
For now, let's say a reference is "dubious" if it doesn't begin with `#`
and it has no `.` anywhere.
Originally I called this `dotless` but I imagine the heuristic could change,
so let's just give the heuristic a name and we can adjust it.

Normal references normally have a dot, e.g.,
in the URL domain name or to introduce a file extension.
It's not strictly *required*, but as a warning of a potential problem,
it's not a bad heuristic.
The one case where a reference might not have a dot is if it's a pure
fragment URL (e.g., `#see-also`); that might be better handled with
element context, but I think we should allow it.

It's easy to add a dot, e.g., you can add `./` before a local directory.
If you use domain `localhost`, adding a period technically changes the
domain from "relative" to "absolute" but in *practice* it'll end up
with 127.0.0.1 either way. Or you could disable this setting.

Add this to the set of values you can set with `caseproc-config` - valid
values are `true` or `false`. Then you can set it in the doc.

## Check for escapes when writing LTAC, fix and test

It's legal for an LTAC statement to end in {...} or (...), you just have
to add an empty one afterwards if necessary to escape it.
However, I don't know that we write the escapes when we write LTAC files.

Verify that we can read and correctly rewrite LTAC examples like this, and
if not, fix it. We should only add the empty escapes when we need to.
Here are some examples:

~~~~
- Claim C1: Foo (really a foo) ()
  - Claim C2: Bar {really a bar} {}
  - Claim C3: Baz (really a bar) {needsSupport}
  - Claim C4: Fizz (fizz.txt)
~~~~

## Look for unnecessary changes in LTAC extensions text

File `docs/ltac-extended.txt` was modified from `docs/ltac.txt` with
our extensions. We want to keep the changes that add new functionality,
fix spelling errors, add clarifications, etc. However, maybe there
are some lines that didn't need to change. Identify which lines
could be restored to exactly their original form without loss
(e.g., maybe they break lines differently).

Don't *implement* the changes yet - just identify them for review.
