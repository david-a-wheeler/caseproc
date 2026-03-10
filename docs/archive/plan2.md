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
Replace its position with `--stdout`, which processes the Markdown/HTML
file(s) and sends them concatenated to stdout (this is the former default).
Normally users will update the LTAC and the content files (Markdown/HTML),
then they'll run this tool to fix everything up.

In most cases we will process 1+ content files.
If 1+ content files are specified on the command line, use those.
Otherwise, use any specified in the config file (if any are).
Otherwise, if files are unspecified, and not given in the config file,
look for the file `case.md`, `case.html`, `docs/case.md`, and
`docs/case.html` in that order; if found, use that file.
If none are found, panic with an explanation.

We want to make it easier for the program to rewrite LTAC files, but only
when specifically told to do it.
To make that easier, remove support for "//" comments
in LTAC, and require LTAC to use "-" bullets (stop supporting `*` bullets).
This is technically a breaking change but no current users use it, and
we've already updated the extended LTAC spec to reflect this change.

A brief note: it's a design goal that the default operation of the
tool is idempotent.
That is, running it twice with default settings should produce the same result.

In the content files (Markdown/HTML) we already modify text within
marked regions.
In *addition*, we will omit HTML anchor lines of the form `<a id="CASE_ID"></a>`
where the `CASE_ID` is the GitHub ID possible for an assurance case component
(`package-...`, `claim-...`, `evidence-...`, etc.).
In *addition*, when we see a Markdown header (`#...`) or HTML header
(`<hNUMBER...>TEXT</hNUMBER>`, where the initial text matches
assurance case component type ("Package ID...", "Claim ID...", "Strategy ID..."),
then just before that
we will re-insert HTML anchor lines with just the component type "-" ID
in GitHub's format, e.g., "Claim Foo Bar" would become
`<a id="claim-foo-bar"></a>`.
Note that this means the tool stays idempotent - we remove possibly-obsolete
anchor lines, and re-insert anchor lines once we know what the correct
ones are.
We'll modify the mermaid and generated LTAC hyperlinks to link to simply
component type "-" ID, e.g., `claim-foo-bar`; that way, the graphics
and generated LTAC hyperlinks will work even if a statement changes.
Currently, we update the header statement if it's out of date for its ID,
as long as `update` is true. Let's rename `update` to `update_headers`
in the configuration, and make that true by default.

Now that the `--update` command flag no longer influences Markdown/HTML
headers, I want to radically change its meaning.
This is a backwards-incompatible change, but I'm the only user today
so that's fine.

I want `--update` to mean that we will update the *LTAC* file.
When `--update` is selected, after reading and validating the LTAC file,
rewrite the LTAC file so that any Link or Citation with a statement
is changed to use the *defining* element statement (considering the statement
of defining element as the canonical version).
That is, if a citation has a statement AND it's a
different statement, it'll be updated to the current statement.
Otherwise, statement discrepancies in the LTAC file
are warned about, with a note saying
"To update LTAC statements to match their declarations, use `--update`."
or something like that.

We will add
a --rename "OLD" "NEW" for renaming a label everywhere from OLD to NEW.
Do validate first before any rename or restate,
just to make sure there are no weird problems.
Before each rename operation, we must
ensure that OLD is used and NEW is not already used at the
time of the operation. This operation
also fixes content docs (headers, anchor names, and marked regions).
You can use multiple `--rename` options.
If it fails (there is no OLD declared in the LTAC file
or NEW is already declared in the LTAC file),
then the entire command fails as a panic
and all files are unchanged.
If all succeeds it will eventually update the LTAC file and content docs.

We will add
a --restate "LABEL" "STATEMENT" for changing statement to STATEMENT
in the LTAC file.
You can use multiple `--restate` options.
If LABEL doesn't exist at the time of operation,
then the entire command fails as a panic
and the files are unchanged.
If all succeeds it will eventually update the LTAC file and content docs.

If there are restate or rename operations, then once
all restate and rename operations have been successfully
processed for the input LTAC,
the tool will write out the proposed updated LTAC and
update the batch of content docs with the same operations
(headers, anchor names, and marked regions).
Within each content doc, the restates and renames are applied in order to
any header, to ensure that they end up with the correct result.

NOTE: You can use *both* `--restate` and `--rename` in the same command,
and multiples of either of them or both of them. Thus, we must use Python's
argparse specially to implement ordered mixed options.
Its action='append' won't do it, as that won't record the possibly
interleaved order between them.
We'll need a custom action that appends
tagged tuples to a single list (e.g., ('rename', old, new) or ('restate',
label, stmt)).
It should be possible to swap label definitions by using an intermediary,
e.g., `--rename FOO BAR_TOBE --rename BAR FOO --rename BAR_TOBE BAR`
would swap FOO and BAR.
The rename and restate operations are applied in order, each seeing
the state produced by the previous one.
Be careful on this implementation, and be sure to have a stress test
to work it.

Most of the time the LTAC file is processed only as input.
However, the `--update`, `--rename`, and `--restate` options
modify the LTAC file in place,
providing many of the benefits of a database-based approach without the hassle.
In all cases the system processes all options, then validates the LTAC,
and only *then* (once it passes validation) will it apply operations that
modify the LTAC in place. That way, we aren't modifying corrupt files.
After any LTAC-modifying process, do a re-validation of the LTAC
internal data structures
to make sure our data structures are okay before writing out our updated version
to a temporary file
(which will soon replace the original version).
I currently expect that we'll regenerate the LTAC file by writing it out.
When regenerating the LTAC, put a blank line between each package,
and keep them in the same order as when they were originally specified.
Test to verify this.
Once the LTAC is modified, the content files (Markdown and HTML)
are updated. The generated graphics, LTAC, etc., all use the new LTAC data.
The headers undergo the sequence of renames and restatements and use the
defined statement for whatever their final label is - that way, the
Markdown and HTML is kept consistent with the LTAC file.

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
This only records *one* backup, but we expect people will use version
control to record more.
This functionality should be implemented by a few small simple functions.
