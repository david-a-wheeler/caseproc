updated # Plan 3: Auto-generate document headers

## Tweaks

Let's begin by first making a few smaller changes:

* In the LTAC spec `docs/ltac-extended.txt` completely remove the
  [PackageIdentifier] notation from ExternalIdentifer. This changes it from
  `ExternalIdentifier = "^" [ "[" PackageIdentifier "]" ] LocalIdentifier ;`
  to `ExternalIdentifier = "^" LocalIdentifier ;`
  LTAC identifiers are globally unique, so
  we don't need to specify the package at all.
  Indeed, globally unique identifiers make many things simpler.
  This change also eliminates figuring out the "conventional" name of a
  package in the spec.
  Note that you can still refer to an external identifier anywhere in a package
  (not just at the top).

  We need to remove the code that supports this notation from `caseproc`
  and change tests that use it. We want to simplify things!

* Whenever generating the LTAC or documents, be sure to use its line-ending
  conventions (either CRLF or LF). The first line of the file determines
  the convention. We could guess LF, but I don't know of a case where have
  to guess; in this new model, we only replace code in documents after we
  have a marker (so we know where to start), and if we're updating an LTAC
  file, we use its current convention. We do this for each file (they might
  differ).

Let's create a short routine that creates a hyperlink from `content`
to `URL` given `format`, where format is `markdown` or `html`.
For markdown it generates `[escaped content](link)`, while for html
it generates `<a href="link">escaped content</a>`.
It escapes content as necessary for that format.
We'll use this routine often in the work to follow.

After we've done that, let's focus on our main improvement.


## Main improvement

Currently our process for handling headers is convoluted and
different than everything else.
We have to look for markdown/HTML headers, filter out
certain anchors, etc. Our search has to identify specific English
names in headers, tying it English.

Let's *remove* all code for detecting document headers (`#...` and `<hNUMBER>`)
and for replacing the equivalent anchors. In its place, let's
create 2 new selectors `element` and `package`.

The selector `element ID` generates at least the following
when we are processing a markdown document (where `ELEMENT_TYPE`, etc.,
are placeholders):

~~~~markdown
<a id="COMPONENT_ANCHOR_ID"></a>
### ELEMENT_TYPE ID: ELEMENT_STATEMENT

~~~~

Where `COMPONENT_ANCHOR_ID` is determined by `_component_anchor_id`
from the element type (such as `claim`) and the LTAC ID.
E.g., for a Claim with ID `Foo Bar` this becomes `claim-foo-bar`.
IDs are already required to have unique GitHub IDs, so this will be unique.

The same selector would generate at least the following
when we are processing an HTML document:

~~~~html
<h3 id="COMPONENT_ANCHOR_ID"
>ELEMENT_TYPE ID: ELEMENT_STATEMENT</h3>

~~~~

This means we need to know if we're processing markdown or HTML while
updating a document file.
A file ending in `.md` or `.markdown` (ignoring case) is markdown.
A file ending in `.htm` or `.html` (ignoring case) is HTML.
We'll guess standard input (`-`) is markdown.
Anything else is a panic.
In --stdout mode, the input determines the output type.

The heading level (number of `#` in markdown or the number in `<hNUMBER`
in HTML) is determined by
the config value `element_level`, which defaults to 3.

In the past we tracked the "current element". Let's make that the
"current ID"; using either of these new "element" or "package" selectors
*sets* the current ID. In the case of package `*`,
the system loops through each package, setting the "current ID" each time.
that way, when it calls other selectors to generate the package contents,
they'll have the correct one. After `*` ends, the "current ID" would be
the last package presented.
We don't allow `*` instead of ID, that wouldn't make sense, though
we will continue to do this for `package`.

I said the selector element generates at least, because what it generates
after that would depend on the config value `element_selections`.
This is a comma-separated list of zero or more
selection names, which will be applied
in order after this. They'll each use the "current id" to determine
what to apply this to (as that was set by `element`).

By default `element_selections` will have the value
`referenced_by,supported_by,supports`.

Here is the markdown version of each of those selections:

`referenced_by` (for markdown):
~~~~
Referenced by: (hyperlinked list of packages containing it, starting with
  the package that defines it in bold, followed by all packages that cite it,
  in LTAC file order, comma-separated)

~~~~

`supported_by`:
~~~~
Supported by: (starting with this element's definition in bold, a
hyperlinked list of all its children elements, including cited and link
elements, comma-separated)

~~~~

`supports`:
~~~~
Supports: (hyperlinked list. First it's the parent of this element's
  definition in bold, followed by the list of all parents of citations of this
  element in LTAC file order. If it's a top-level item with no direct
  parent, just omit the parent.)

~~~~

If we're generating HTML, all of these generate the HTML version of the same
thing as the markdown, e.g., `<a href="LINK">CONTENT</a>` instead of
`[CONTENT](LINK)`.

As a result, a single `element` selector can generate a header
and a lot of infomration, and exactly what information is generated
is easily controlled in one place.

Similarly, the selector `package ID|*` generates in markdown at least:

~~~~markdown
<a id="COMPONENT_ANCHOR_ID"></a>
### Package ID: Statement

~~~~

The leading `<a id...` is technically HTML, but markdown doesn't have
a standard way to force HTML ids, so we'll do it this way.

The "Component" type in this case is "Package", so the component anchor
for package `foo bar` would be `package-foo-bar`.
The statement would be statement of the topmost element.
If there's no statement, don't show the ": " either.
GitHub's markdown processor inserts hypertext IDs, and many others do too,
but not all; by forcibly including the anchor, we *know* it will be there.
If the markdown processor generates anchors, *and* the top-level element
of a package has no statement, we'll end up with 2 HTML ids in basically
the same place; that's unfortunate, but acceptable as it ensures it will work.
We already require all ID to have unique GitHub ID representations,
so this shouldn't be a problem.

The config value `package_level` controls level of the heading
for markdown or HTML, which starts at 3. This is similar to `element_level`.

In HTML it would generate at least:
~~~~html
<h3 id="COMPONENT_ANCHOR_ID">Package ID: ELEMENT_STATEMENT</h3>

~~~~

Where `COMPONENT_ANCHOR_ID` uses the type `package`.

Note that every time this `package` selector generates a header it
sets the "current id" value to that ID
(we previously called this the "current element").

Similarly, what `package` generates after that header
would depend on the config value `package_selections`.
This is a comma-separated list of zero or more
selection names, which will be applied
in order after this header for each header. They'll each use the "current id".

By default `package_selections` will have the value
`representation,pkg_defines,pkg_citing,pkg_cited`.

The `representation` selector, whenever used,
applies whatever selection is stored in
the config value `default_representation`, which defaults to `sacm`.
That way, users can easily change just the config value
`default_representation` to `gsn` and they'll get gsn for every package.
Users don't *have* to change it, then they'll just get the default.

Let's extend the selector syntax to three parts: `NOTATION/RENDERER/FORMAT`,
filling in defaults right-to-left based on the document type:

| Written | Interpreted as |
|---|---|
| `sacm` | `sacm/mermaid/{doc-format}` |
| `sacm/mermaid` | `sacm/mermaid/{doc-format}` |
| `sacm/mermaid/markdown` | explicit |
| `sacm/mermaid/html` | explicit |
| `gsn` | `gsn/mermaid/{doc-format}` |
| `gsn/mermaid` | `gsn/mermaid/{doc-format}` |
| `gsn/mermaid/markdown` | explicit |
| `gsn/mermaid/html` | explicit |
| `ltac` | `ltac/{doc-format}` |
| `ltac/markdown` | explicit |
| `ltac/html` | explicit |

`ltac` has no separate renderer level (its renderer is its format),
so it stays two-part. The rule is: fill in missing parts from the right
using the document type.

We'll keep the explicit variation names in case the user needs to force
the use of a specific format.

`sacm/mermaid/html` and `gsn/mermaid/html` generate `<pre class="mermaid">`
blocks (the Mermaid v10+ standard):

~~~~html
<pre class="mermaid">
flowchart BT
  ...
</pre>
~~~~

Add a config key `mermaid_js_url` with the default value:

```
https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs
```

When generating a Mermaid diagram in an HTML document, caseproc checks
whether the document already contains a `<script` tag referencing the
`mermaid_js_url`. If not, it injects the following block immediately
before the first generated `<pre class="mermaid">`:

~~~~html
<script type="module">
  import mermaid from 'URL';
  mermaid.initialize({ startOnLoad: true });
</script>
~~~~

Setting `mermaid_js_url` to `""` disables auto-injection entirely,
for users who manage the script themselves in their HTML template.

We inject before the first diagram rather than into `<head>` because
caseproc doesn't require a valid full HTML document structure;
injecting into `<head>` would require parsing/locating it, while
injecting before the first diagram is always correct and works in
partial HTML files.

The `pkg_defines` selector shows the word `Defines: `,
followed by a comma-separated list of "TYPE ID" (e.g., "Claim Foo")
that has a hyperlink to its header (`#TYPE-ID`),
followed by a blank line. These are all of the elements that are
*defined* in this package (don't use `^`), starting with the top element
(which is normally a claim). Bold the top element, to emphasize
its special status. Markdown bolds with `**..**`, HTML with `<b>...</b>`.
Thus, we can easily jump from here
to the details of any element defined in this package from the
representation *or* this list.

The `pkg_citing` selector shows `Citing: `,
followed by a comma-separated list of "TYPE ID" (e.g., "Claim Foo").
These are all of the elements that are citing (`^`) within this package,
with a link to the *package* that defines it
(even if it's also *defined* in this package, a weirdness we allow).
This means that users who see one figure can click on a citation, which
will bring them to the figure that shows its definition.
From *that* figure they can click on its definition to see its details.
For a citation
we can't easily know if the user wants to see the package with the element
definition, or the details about that element.
So we'll presume the user wants to see the package, and
from there the user can see it in context and select its definition to
see its details.
Again, a blank line follows.

The `pkg_cited` selector shows `Cited by: `,
followed by a comma-separated list of "Package ID" (e.g., "Package Foo"),
where "ID" is the ID of a package's topmost element.
These are all of the packages in the assurance case
that include a cite (`^`) to an id that is defined within this package,
even if that's this package.
Its link is to the *package*.

Note that these all share the same heading.

I've expressed "followed by a blank line" or showed trailing blank lines
everywhere. When it's in a generated segment, let's suppress the very last
blank line at the end of what's generated, so we don't have lots of
useless blank lines.

Note that `package *` is the expected use, and this single directive
can generate a *lot* of text (multiple headers, each with graphics, links,
etc.) That is *expected* behavior - we will get a lot of results with
a simple directive.

Currently, per reference.md, --validate
"cross-checks their headers against the LTAC."
Instead of cross-checking *headers*, it now cross-checks against the
*element* declarations, listing elements not currently included.
Basically, it validates that every
declared LTAC element has a corresponding element selector.

The `update_headers` config key becomes obsolete with this change,
so we'll remove the config item and the code for it.

Migration strategy:
This hard-removes header scanning. Existing documents using headers
(### Claim C1: ...) will break. We don't have users yet, so I'm not worried
about transition periods. However, we should build a simple transition tool
so we can convert our test suite efficiently.

## Dynamic modification of config values

Let's make it possible to modify a config value dynamically.
That'll be especially useful, for example, for the heading levels.

To do this, we'll create a special directive `config` with this syntax:

`<!-- caseproc-config KEY = VALUE... -->`

Note that VALUE is everything up to the first `-->` - it can contain spaces.
The VALUE is trimmed of whitespace on the left/right side.
That means we can't set leading/trailing whitespace, but we can add
facilities to do that later if that's important.
Currently we don't expect that to be important.

There's no reason to end it, so in this case we won't look for
`<!-- end caseproc -->`.
We'll use the slightly different `caseproc-config` instead of `caseproc`,
and call this a directive and not a selector,
so it's distinct from the selectors that *do* require `end caseproc`.
If someone accidentally uses the *selector* `config`, report that as
an error and explain that `caseproc-config`, not `caseproc config`, is
the correct syntax.

We expect `caseproc-config`
to only be used in documents and only to be used
outside the marked regions of selectors.
It would be ignored and replaced if it was inside a region, like
any other text in a marked region.

This special directive first checks if KEY is allowed to be changed, and
that it's allowed to be changed to VALUE.
If not, it prints a warning message that it can't change KEY to VALUE
at that document and line.
If it is, this special selector immediately sets config KEY to VALUE,
which will last until changed again.

We'll check if it's "allowed to change" by first seeing if it *has*
a default config value - if not, we don't know about it, reject.
If it does, consult a dictionary `allowed_values` which maps keys to
a regular expression of allowed values.
For now we'll just allow setting of `element_level` and `package_level`,
in both cases `^[1-6]\Z`.
We can allow more later.

The directive is itself preserved in the output.
It takes effect immediately, and persists.
It is even applied during `--validate`.

## Other updates

We'll need to update tests, `--help`, and `docs/reference.md` among other
places.

## Option to add missing elements to documents

Let's add a new option `--missing`. This will simplify handling
missing element information.

When `--missing` is run, it will still update the document as usual.
It will also notice when an element appears to have no user-created content.
An element "appears to have no user-created
content" if the text between its `<!-- end
caseproc -->` closing marker and the next `<!-- caseproc element ` or `<!--
caseproc package` directive consists only of blank lines and other caseproc
and caseproc-config directives.

Once it reaches the `</body>` of
the last doc if it's HTML, or the end of the last doc no matter what,
it will insert region markers for every element ID that has
not been in any document. That is, it will add:

~~~~
<!-- caseproc element ID -->
(contents of caseproc element ID as usual)
<!-- end caseproc -->

~~~~

It will then go through each element that was either missing or appears
to have no user-created content.
Every element that
(1) has no other assertionDeclaration (the default is considered `asserted`),
and (2) is a leaf element in its definition,
will have the option `needsSupport` added.
If at least one element has had a new `needsSupport` added,
the updated LTAC is then written back.
As with all changes of files, this will use the safe backup mechanism.

Basically, by running `--missing`, we add all markers missing in the document,
and we ensure that the user can see the elements that probably most
need information.

## Discussion

Let's remove the selectors references info - they're getting superceded.
The `statement` selector might be useful, let's keep it. It supports an
optional ID - if ID is omitted, current component (most recently invoked)
is used.
