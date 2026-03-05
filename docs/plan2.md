# Plan 2

After experimentation and review, I want to make it much easier to
use the caseproc tool.
I want to focus on streamlining normal use, make it easier to manipulate
the LTAC file through the tool but only when the user commands it,
and clarify the roles of the LTAC file vs. the Markdown/HTML file(s).

Simply running `caseproc` with no options should "do the right thing",
that is, process the input LTAC file and update the content files
(the Markdown/HTML files), using a default config file if one is defined.

So, if no "config" file is chosen with `--config`, look for a default
`case.config` else a `docs/case.config` file, and load that.
Try to load the config file before loading the ltac file.

In the config file:
- add a new ltac_file= keyword that can give the filename of the LTAC file
  (this implements --ltac FILENAME though its value
  can be overridden on the command line. This value is optional).
- add a new content_files= keyword that can accept a list of filenames
  (the Markdown/HTML files),
  which if set will be processed as the "files" on the command line unless the
  command line gives a different list. This value is optional.

Eliminate the `--inline` (-i) flag, make that functionality the default.
Replace its position with `--filter`, which processes the Markdown/HTML
file(s) and sends them concatenated to stdout (this is the former default).
Normally users will update the LTAC and the content files (Markdown/HTML),
then they'll run this tool to fix everything up.

In most cases we will process 1+ content files.
If 1+ content files are specified on the command line, use those.
Otherwise, use any specified in the config file (if any are).
Otherwise, if files are unspecified, and not given in the config file,
look for the file `case.md`, `case.html`, `docs/case.md`, and
`docs/case.html` in that order; if found, use that file.
If none are found, panic with error.

We want to make it easier for the program to rewrite LTAC files when
specifically told do. To make that easier, remove support for "//" comments
in LTAC, and require LTAC to use "-" bullets (stop supporting `*` bullets).

In the content files (Markdown/HTML) we already modify text within
marked regions.
In *addition*, we will omit HTML anchor lines of the form `<a id="CASE_ID"></a>`
where the `CASE_ID` is the GitHub ID possible for an assurance case component
(`package-...`, `claim-...`, `evidence-...`, etc.).
In *addition*, when we see a Markdown header (`#...`) or HTML header
(`<hNUMBER...>TEXT</hNUMBER>`, where the initial text matches
assurance case component type ("Package ID.."Claim ID...", "Strategy ID..."),
then just before that
we will re-insert HTML anchor lines with just the component type "-" ID
in GitHub's format, e.g., "Claim Foo Bar" would become
`<a id="claim-foo-bar"></a>`.
We'll modify the mermaid and generated LTAC hyperlinks to link to simply
component type "-" ID, e.g., `claim-foo-bar`; that way, the graphics
and generated LTAC hyperlinks will work even if a statement changes.
Currently, we update the header statement if it's out of date for its ID,
as long as `update` is true. Let's rename `update` to `update_headers`
in the configuration, and make that true by default.
Change the `--update` command line option to temporarily print
`update option shown`; we'll later implement something else with that option.

Now that the `--update` command flag no longer influences Markdown/HTML
headers, I want to change its meaning.
I want `--update` to mean that we will update the *LTAC* file.
When `--update` is selected, after reading and validating the LTAC file,
rewrite the LTAC file so that any Link or Citation with a statement
is changed to use the *defining* element statement (considering the statement
of defining element as the canonical version).
That is, if a citation has a statement AND it's a
different statement, it'll be updated to the current statement.
Otherwise, statement discrepancies in the LTAC file
are warned about, with a note saying
"To update LTAC statement information automatically, use the option --update`

We should add
a --rename "OLD" "NEW" for renaming a label everywhere from OLD to NEW.
Do validate first, just to make sure there are no weird problems, and
to ensure OLD is used and NEW is not already used. Then fixes content docs.
You can use multiple `--rename` options.

A --restate "LABEL" "STATEMENT" for changing statement to STATEMENT.
Then fixes content docs.
You can use multiple `--restate` options, but you can't use
`--rename` and `--restate` in the same command (we'd then have to track
their order, Python's processing system makes that harder).

Most of the time the LTAC file is processed only as input.
However, the `--update`, `--rename`, and `--restate` options
modify the LTAC file in place,
providing many of the benefits of a database-based approach without the hassle.

Whenever doing an in-place edit (LTAC, Markdown, HTML), generate the files
first as temporary files.
Then output to standard error "Updating FILENAMES" (list them).
To implement the replacement, move the old files to the subdirectory
`.backup/` (creating it if doesn't exist).
then move the updated files from their temporary locations to their
final filenames. That way, if the program
crashes or something during processing before the update, nothing 
bad happens to those files. If something really awful happens, we will
still have a copy of the previous version.
This functionality should be implemented by a few small simple functions.
