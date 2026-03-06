# Plan 3: Auto-generate document headers

## Goal

Currently our process for handling headers is convoluted and
different than everything else.
We have to look for markdown/HTML headers, filter out
certain anchors, etc. Our search has to identify specific English
names in headers, tying it English.

Let's *remove* all code for detecting headers (`#...` and `<hNUMBER>`)
and anchors. In its place, let's
create 2 new selectors `element` and `package`.

The selector `element OPTIONS ID` generates in markdown:

~~~~markdown
<a id="ELEMENT_TYPE-ID">
### ELEMENT_TYPE ID: ELEMENT_STATEMENT

Referenced by: (hyperlinked list of packages containing it, starting with
  the one it's defined in, comma-separated)

Supported by: (hyperlinked list of children elements of definition)

Supports: (hyperlinked list of parents of the definition and all citations)

~~~~

The OPTIONS could be nothing, I'm currently thinking of using `-` for
"no options" (suggestions welcome). A number would be the level of the
heading (configurtion option `element_header_level` default value 3) -
we show `###` here which is 3.

We need to know if we're processing markdown or HTML.
A file ending in `.md` or `.markdown` or is `-` (standard input) is markdown
(ignoring case).
A file ending in `.html` or `.htm` is HTML.
Anything else is a panic.

The configuration shoudl have a default OPTIONS value.
The options should eventually let us select "what is generated in an element".

The selector `package OPTIONS ID` generates in markdown:

~~~~markdown
<a id="package-ID">
### Package ID

Top ELEMENT_TYPE: ID (hyperlinked)

(Package representation)
~~~~

The configuration value `package_representation` declares a comma-separated
list of representation(s) are shown to represent the package.
Currently it can be sacm, gsn, or ltac.

Let's add new selectors sacm, gsn, and ltac. Each of them select
the `/markdown` or `/html` variations of them depending on whether or not
the containing document is markdown or html.

We'll need to update tests, `--help`, and `docs/reference.md` among other
places.
