# Plan 10

Let's add some more validations; they're warnings unless noted otherwise.

1. Check each package to see if starts with a Claim or Justification,
and warn if it starts with anything else.

2. Warn of every incidence of Evidence with children.

3. If an element has no ID *and* no statement, report it as an error
(including its line). It can't possibly contribute to anything.
I believe we already complain about Link with no ID, as it's syntactically
required.

4. Empty statements are fine for Link, Relation, or any citations (^).
Any other kind of declaration, other than Link or Relation,
usually has a statement.
As you parse the LTAC file, track as you go if you see (1) an empty statement
in kind of declaration that usually has a statement, and
(2) a non-empty statement in a kind of declaration that usually has
a statement.
If at the end of processing both values are true,
issue warnings to list all of the IDs of declarations with empty statements.
Don't include the ones with no ID *and* no statement, that's covered separately.
I mention the tracking as you go
because this should be easy to do, and it lets
us skip re-checking everything in the common case where there is
nothing to report.
Note that this means we intentionally won't complain 
if we read a demo which consistently has no statements; the point is to
complain when there are *some* statements but not in all cases where we
would expect them.

5. Two `- Link X` entries under the same parent cite the same element twice,
which is redundant and probably a copy-paste error.
This appears to be distinct from the existing duplicate-sibling-identifier
check, which covers declared elements and ^ citations but
might not cover Link nodes. If it's already covered, great.
See lines 518–519, Link nodes are routed to
`self._links.append(...)` and the entire sibling-identifier-check block (lines
570–582) is skipped for Links. So two - Link X entries under the same parent
will currently pass undetected. New check or modification of existing check
is needed.

Note that checking for an ^ID with no matching declaration
is already covered by our validations (line 2632).
