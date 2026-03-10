Mermaid doesn't handle wide constructs well. Let's discuss creating an
addition for both GSN and SACM for *rendering* (this transformation only
happens during rendering, and must not modify the original data structures).

## Stage 1: Make GSN render Connector visibly (prerequisite)

Currently `Connector` in GSN is completely transparent: `_gsn_node_decl`
returns `''` for it, and `_gsn_collect_edges` flattens its children
directly to the grandparent as if the Connector weren't there.
This is fine for LTAC-authored Connectors in GSN (GSN has no grouping
concept), but it means synthetic Connectors created for width management
(Stage 2) would do nothing in GSN — the overflow children would just
appear as additional siblings, leaving the diagram equally wide.

We fix this before implementing Stage 2.

**Changes to `_GSN_HEADER`:** add the same `classDef` used by SACM:

```
    classDef connector fill:none,stroke:#cccccc,stroke-width:1px;
```

**Changes to `_gsn_node_decl`:** return a node declaration for Connector
instead of `''` — same gray-circle shape as SACM:

```python
if node.node_type == 'Connector':
    return f'    {node.diagram_id}(("{_HAIR_SPACE}")):::connector'
```

**Changes to `_gsn_collect_edges`:** instead of flattening Connector's
children to the grandparent, emit a `parent --> connector` edge and then
recurse into the Connector's children normally (so they get
`connector --> child` edges):

```python
elif child.node_type == 'Connector':
    edge_lines.append(_edge_line(node.diagram_id, child.diagram_id,
                                 False, False, False))
    _gsn_collect_edges(child, edge_lines, leaf_nodes)
```

No existing test fixtures use Connector, so this change carries zero
fixture-update cost.  Add a test that verifies a Connector in a GSN
diagram produces a visible node declaration and edges through it (rather
than being transparent).

## Stage 2: Width-management transform

If we're rendering a diagram, we may do some
transformations specifically for that kind of notation.
Ensure we make enough of a copy that we don't mess up the original data,
as we make some temporary additions purely for visual improvement.
A shallow copy won't be enough; if a deep copy is necessary, that's okay.

In SACM, `_sacm_collect_edges` already performs the Strategy-absorption
transform for every Strategy, unconditionally (not just when it is the
sole child).  When a Claim has a Strategy child, the Strategy's
non-Context children are added directly to the Claim's `inference_sources`,
and the Strategy itself is appended last — making it a sibling of its
former children behind the same sacmDot.  For example, this LTAC:

~~~~
- Claim Top
  - Strategy S1
    - Claim C1
    - Claim C2
    - Claim C3
    - Claim C4
~~~~

is already rendered as if it were (using a conceptual sacmDot node to
represent the sacmDot grouping — this is internal rendering, not LTAC syntax):

~~~~
- Claim Top
  - sacmDot (auto-generated)
    - Claim C1
    - Claim C2
    - Claim C3
    - Claim C4
    - Strategy S1
~~~~

Stage 2 does **not** need to implement this transform; it is already done.
The width-management transform simply counts the `inference_sources` list
that feeds each sacmDot, since that is what is already "visually expressed"
after the absorption.

For all mermaid processing,
let's look for cases where there are more than
`max_mermaid_children` (default 8)
children that will be rendered on the visual image.
For SACM, this means the inference_sources list feeding each sacmDot.
In SACM, each sacmDot's `inference_sources` list is checked separately
(context children form their own group and are not counted together with
inference children, since they are visually separate).
This "max children" is used for anything that has *visually* expressed
children.

In those cases, keep `narrowed_mermaid_children` (default 6), the leftmost
and rightmost maximally even totalling up to that number.
Add a Connector link in the
middle (between the kept children; if we have an odd number, prefer fewer
on the left). The Connector will have as children the remaining children.
Then the algorithm recurses (we could have several layers).
E.g., with 9 children, we would have [0,1,2, Connector(3,4,5), 6,7,8].
We do this intentionally, because mermaid naively renders left-to-right;
if we put them on the edge, mermaid would end up taking *more* room
on the screen (what we're trying to avoid).

We need to give these Synthetic Connectors names that are okay for
Mermaid but unlikely to interfere with real IDs.
Use `SynConnect_` followed by a random 8-digit hex number.

So continuing the example, if `max_mermaid_children` is 4,
and `narrowed_mermaid_children` is 2, we'd end up with:

~~~~
- Claim Top
  - sacmDot (auto-generated)
    - Claim C1
    - Connector SynConnect_0a0a0a0a
      - Claim C2
      - Claim C3
      - Claim C4
    - Strategy S1
~~~~

If `max_mermaid_children` is 0, the algorithm immediately returns and
makes no transforms.

Add the bottompadding *after* this (and other transforms).

Let's ensure that caseproc-config can change these values
`max_mermaid_children` and `narrowed_mermaid_children`.
For the value checks, they must be integers, e.g.  `^(0|[1-9][0-9]*)\Z`.
Check that.

This discussion presumes the configuration values satisfy the invariants
`narrowed_mermaid_children < max_mermaid_children` (so things improve)
and `narrowed_mermaid_children >= 2` (so there's enough room).
Let's create a routine `config_invariant_checker`.
The routine will check that invariant, and panic with message if it's wrong.
We'll call the routine
after we've had the opportunity to load the configuration file
(we'll *always* call it, just in case our code is messed up).
We'll also call this routine every time caseproc-config changes a value.

Add tests, fix the --help text, and modify docs/reference.md to match.
