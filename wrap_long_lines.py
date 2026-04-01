#!/usr/bin/env python3
"""Paragraph-aware line wrapper for verocase.py comments and docstrings.

Uses the system fmt command for reflowing. Only touches:
- Consecutive comment lines at the same indent level (comment blocks)
- Consecutive prose lines inside docstrings (docstring paragraphs)

Skips: doctest lines, lines with URLs, lines with backslashes,
opening/closing triple-quote lines, bullet/list lines, short overages.
"""

import ast
import re
import subprocess
import sys

MAX_LEN = 80


def find_docstring_lines(src: str) -> set:
    """Return set of line numbers (1-based) inside actual docstrings only.

    Uses the AST to identify only true docstrings (first expression in a
    module, class, or function body), not data strings like Mermaid CSS.
    """
    result = set()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return result
    for node in ast.walk(tree):
        if isinstance(
            node,
            (
                ast.Module,
                ast.ClassDef,
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                ds = node.body[0]
                for ln in range(ds.lineno, ds.end_lineno + 1):
                    result.add(ln)
    return result


def get_indent(line: str) -> str:
    return re.match(r"^(\s*)", line).group(1)


def fmt_comment_block(lines: list, max_len: int) -> list:
    """Reflow a block of # comment lines using fmt."""
    if not any(len(l.rstrip()) > max_len for l in lines):
        return lines
    indent = get_indent(lines[0])
    prefix = indent + "# "
    text = "".join(lines)
    result = subprocess.run(
        ["fmt", f"-p{prefix}", f"-w{max_len}"],
        input=text, capture_output=True, text=True,
    )
    reflowed = result.stdout.splitlines(keepends=True)
    if not reflowed:
        return lines
    # Safety checks: all lines must start with indent+# and fit
    if not all(l.startswith(indent + "#") for l in reflowed if l.strip()):
        return lines
    if any(len(l.rstrip()) > max_len for l in reflowed):
        return lines
    return reflowed


def fmt_docstring_para(lines: list, max_len: int) -> list:
    """Reflow a prose paragraph inside a docstring using fmt."""
    if not any(len(l.rstrip()) > max_len for l in lines):
        return lines
    indent = get_indent(lines[0])
    width = max_len - len(indent)
    if width < 20:
        return lines
    # Strip indent, join as one paragraph, reflow, re-indent
    stripped = " ".join(l[len(indent):].rstrip() for l in lines)
    result = subprocess.run(
        ["fmt", f"-w{width}"],
        input=stripped + "\n", capture_output=True, text=True,
    )
    reflowed = result.stdout.splitlines()
    if not reflowed:
        return lines
    out = [indent + l + "\n" for l in reflowed]
    if any(len(l.rstrip()) > max_len for l in out):
        return lines
    return out


def is_safe_comment_block(lines: list) -> bool:
    return not any(
        "http://" in l or "https://" in l or "noqa" in l
        or l.strip().startswith("#!")
        for l in lines
    )


def is_prose_line(line: str) -> bool:
    """True if this line inside a docstring is safe to include in reflow."""
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith(">>>") or stripped.startswith("..."):
        return False
    if '"""' in stripped or "'''" in stripped:
        return False
    if "http://" in line or "https://" in line:
        return False
    if "\\" in line:
        return False
    # Bullet/list/field markers -- leave alone
    if re.match(r"^\s*[-*]\s", line):
        return False
    return True


def process(infile: str, outfile: str) -> None:
    with open(infile) as f:
        src = f.read()
    src_lines = src.splitlines(keepends=True)
    docstring_lines = find_docstring_lines(src)

    out = []
    i = 0
    n = len(src_lines)

    while i < n:
        lineno = i + 1
        line = src_lines[i]
        stripped = line.strip()

        # --- Comment block ---
        if (
            stripped.startswith("#")
            and lineno not in docstring_lines
        ):
            indent = get_indent(line)
            # Collect consecutive # lines at same indent
            j = i
            while j < n:
                l = src_lines[j]
                if (
                    l.strip().startswith("#")
                    and get_indent(l) == indent
                    and (j + 1) not in docstring_lines
                ):
                    j += 1
                else:
                    break
            block = src_lines[i:j]
            if is_safe_comment_block(block):
                out.extend(fmt_comment_block(block, MAX_LEN))
            else:
                out.extend(block)
            i = j
            continue

        # --- Docstring prose paragraph ---
        if lineno in docstring_lines and is_prose_line(line):
            indent = get_indent(line)
            j = i
            while j < n:
                ln = j + 1
                l = src_lines[j]
                if (
                    ln in docstring_lines
                    and is_prose_line(l)
                    and get_indent(l) == indent
                ):
                    j += 1
                else:
                    break
            block = src_lines[i:j]
            out.extend(fmt_docstring_para(block, MAX_LEN))
            i = j
            continue

        out.append(line)
        i += 1

    orig = sum(1 for l in src_lines if len(l.rstrip()) > MAX_LEN)
    new = sum(1 for l in out if len(l.rstrip()) > MAX_LEN)
    print(f"Long lines: {orig} -> {new}", file=sys.stderr)

    with open(outfile, "w") as f:
        f.writelines(out)
    print("Done.", file=sys.stderr)


if __name__ == "__main__":
    infile = sys.argv[1] if len(sys.argv) > 1 else "verocase.py"
    outfile = sys.argv[2] if len(sys.argv) > 2 else infile
    process(infile, outfile)

