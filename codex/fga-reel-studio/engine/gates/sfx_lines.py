#!/usr/bin/env python3
"""Turn a builder's SFX report (tuples and dict(...) in any layout) into one sound per line.
Run: python3 sfx_lines.py <out.txt> "<report text>" [label]"""
import ast, re, sys
out, text = sys.argv[1], sys.argv[2]
label = sys.argv[3] if len(sys.argv) > 3 else ""
items = re.findall(r'dict\([^()]*\)|\(\s*[0-9.]+\s*,\s*["\'][^"\']+["\'][^()]*\)', text)
lines = [f"# {label}"] if label else []
for it in items:
    if it.startswith("dict("):
        lines.append(it)
    else:
        lines.append(repr(tuple(ast.literal_eval(it))))
open(out, "w").write("\n".join(lines) + "\n")
print(len(items), "sounds ->", out)
