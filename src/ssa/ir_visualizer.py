import re
from typing import Iterable

from src.ssa.helpers import color_label


def _htmlify_lines(lines: Iterable[str]) -> str:
    return '<br ALIGN="LEFT"/>'.join(line for line in lines)


def ir_to_graphviz(ir: str, name: str = "IR") -> str:
    ir = ir.strip()
    if not ir:
        return f"subgraph {name} {{}}"

    # Split on pattern: blank line(s) followed by ; pred: ...
    # This correctly handles blank lines within blocks (they won't be followed by ; pred:)
    # Use positive lookahead to not consume the ; pred: line
    blocks = re.split(r"\n\s*\n(?=\s*;\s*pred:)", ir)
    blocks = [chunk.strip() for chunk in blocks if chunk.strip()]

    nodes: list[tuple[str, str]] = []
    edges: list[tuple[str, str]] = []

    for block in blocks:
        lines = [line.rstrip() for line in block.splitlines()]

        label_line = next(
            (line for line in lines if re.match(r"\s*BB[^:]*:", line)), None
        )
        if label_line is None:
            raise ValueError(f"Cannot find basic block label in block:\n{block}")

        label_match = re.search(r"(BB[^:\s]+):", label_line)
        if label_match is None:
            raise ValueError(f"Cannot parse basic block label from line: {label_line}")
        bb_label = label_match.group(1)

        succ_line = next(
            (line for line in reversed(lines) if line.strip().startswith("; succ:")),
            None,
        )
        if succ_line:
            succ_match = re.search(r"\[([^\]]*)\]", succ_line)
            if succ_match:
                succs = [
                    succ.strip()
                    for succ in succ_match.group(1).split(",")
                    if succ.strip()
                ]
                for succ in succs:
                    edges.append((bb_label, succ))

        nodes.append((bb_label, _htmlify_lines(lines)))

    graph_lines = ["node [shape=box]"]

    for label, html_label in nodes:
        html_label = re.sub(r"(BB\d+)", lambda x: color_label(x[0]), html_label)
        graph_lines.append(f'"{label}" [label=<{html_label}>]')

    for src, dst in edges:
        graph_lines.append(f'"{src}" -> "{dst}"')

    return "\n".join(graph_lines)
