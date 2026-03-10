# Stats and tree manipulation

Let's add some small options.

## Stats

Let's add the new configuration option `stats`, default false.
Let's add the option `--stats`, which after loading the configuration,
this will set this new configuration option `stats` to true.

If configuration option `stats` is true, then after processing, it
reports various statistics (if it read those files).
This won't display if we do no processing (e.g., --help won't show stats).

If we read the LTAC file, show various statistics:
- Number of Elements defined per type (Claim, Strategy, etc.)
- Total number of elements defined
- Total number of citations
- Number of leaf Claims (no children) that aren't citations (^)
- Package with largest number of elements (defined or cited) and how many
- For each option we support, number of elements with that marking
  (e.g., number of elements with needsSupport)

If we processed documents, show more statistics:
- Number of "caseproc package" regions (often 1; if it is 1, note `(typical)`)
- Number of "caseproc element" regions
- Number of elements with no interesting content
  (only blank lines or directives)
- Number of "caseproc-config" statements

If there are some other interesting statistics, suggest them

## Tree manipulators

It'd be nice to make it easy to manipulate the LTAC tree.
Let's add two new options:

`--detach ID`: Replace ID's definition in a tree with a citation of ID,
and create a new package after the current package with its structure.
Panic if `ID` isn't defined or its definition is a top level (package head).

That is, given:

~~~~ltac
- Claim C1: Foo
  - Claim C2: Bar
    - Claim C3: Baz
~~~~

The command `--detach C2` would produce:

~~~~ltac
- Claim C1: Foo
  - Claim ^C2: Bar

- Claim C2: Bar
  - Claim C3: Baz
~~~~

The next option we'll add is `--move ID DESTINATION`, which moves ID's
definition to be a child of DESTINATION. ID may be anywhere in the tree
(top-level or nested). If a `^ID` citation already exists as a direct child
of DESTINATION, it is replaced by the definition; otherwise the definition
is appended as DESTINATION's last child. `--move` does NOT leave a citation
at ID's original location. To leave a citation behind, run `--detach ID`
first (which creates `^ID` in place), then `--move ID DESTINATION`.
Panic if ID isn't defined or DESTINATION isn't defined.

Given the produced LTAC after `--detach C2`, the option
`--move C2 C1` would reverse it and produce our previous LTAC.

Let me clear up a misunderstanding: if ID is also cited elsewhere
in the tree, that is *not* a problem - it would still be cited.
Nothing in the extended LTAC specification requires that citations
only cite an ID that is at the *top* of a tree.
A citation can refer to *any* definition in any tree.
We do require that there be only 1 definition (1 use of ID without ^)
and that there be no cycles, but an ID inside a tree can be cited in
many other places.

The `--detach` and `--move` options
should go into the same queue that
`--restate` and `--rename` use.
If there's more than one such use, they are applied in order.
Add this information to the "--help", and
specifically note the queue that all of these options share
and that their order matters if there's more than one of them.
