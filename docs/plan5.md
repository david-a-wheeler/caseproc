Mermaid doesn't handle wide constructs well. Let's discuss creating an       
addition for both GSN and SACM for *rendering* (this transformation only      
happens during rendering, and must not modify the original data structures).  

If we're rendering a diagram, we make a duplicate, and we may do some
transformations specifically for that kind of notation.
For example, in SACM, an argument that is the sole child of a Claim,
and has children, and ends up being a sibling of its former children
under a sacmDot.

For all mermaid processing,
let's look for cases there are more than `max_mermaid_children` (default 8)   
children that will be rendered from a given node
(which may be a sacmDot).
Note that we consider this *after* we move a SACM Argument to become a sibling.
Note that if in SACM there are different sacmDots, they are considered
separately (e.g., context vs. inference).
This "max children" is used for anything that has *visually* expressed
children.

In those cases, keep the first                
`narrowed_mermaid_children` (default 6), and add a Connector link in the
middle (between the kept children; if we have an odd number, prefer fewer
on the left). The Connector will have as children the remaining children,
and the algorithm recurses (we could have several layers).
E.g., with 9 children, we would have [0,1,2, Connector(6,7,8), 3,4,5]).
We do this intentionally, because mermaid naively renders left-to-right;
if we put them on the edge, mermaid would end up taking *more* room
on the screen (what we're trying to avoid).

If `max_mermaid_children` is 0, the algorithm immediately returns and
makes no transforms.

We presume that we have the invariant
`arrowed_mermaid_children < max_mermaid_children`.
Let's create a routine `config_invariant_checker`.
The routine will check that invariant, and panic with message if it's wrong.
We'll call the routine
after we've had the opportunity to load the configuration file
(we'll *always* call it, just in case our code is messed up).
We'll also call this routine every time caseproc-config changes a value.
