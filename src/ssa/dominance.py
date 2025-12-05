from typing import Optional
from src.ssa.cfg import CFG, BasicBlock
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class DominatorTree:
    entry: BasicBlock
    idom: dict[BasicBlock, Optional[BasicBlock]]
    reversed_idom: defaultdict[BasicBlock, list[BasicBlock]]
    dominators: dict[BasicBlock, set[BasicBlock]]

    def traverse(self, start=None):
        if start is None:
            start = self.entry

        q = [start]
        visited = set()
        while len(q):
            n = q.pop()
            visited.add(n)
            yield n
            q.extend((x for x in self.reversed_idom[n] if x not in visited))


def prune_unreachable(cfg: CFG, reachable_blocks: set[BasicBlock]):
    q = [cfg.exit]
    visited = set()
    while len(q) > 0:
        bb = q.pop()
        visited.add(bb)
        for i in range(len(bb.preds) - 1, -1, -1):
            p = bb.preds[i]
            if p not in reachable_blocks:
                bb.preds.pop(i)
                continue

            if p not in visited:
                visited.add(p)
                q.append(p)


def compute_dominator_tree(cfg: CFG) -> DominatorTree:
    reachable_blocks = set(cfg)
    prune_unreachable(cfg, reachable_blocks)

    dominators = _compute_dominators(cfg.entry, reachable_blocks)
    tree = _build_dominator_tree(dominators, cfg.entry)
    return tree


def _compute_dominators(
    entry: BasicBlock, reachable_blocks: set[BasicBlock]
) -> dict[BasicBlock, set[BasicBlock]]:
    dominators: dict[BasicBlock, set[BasicBlock]] = {}
    dominators[entry] = {entry}

    for block in reachable_blocks:
        if block != entry:
            dominators[block] = reachable_blocks.copy()

    changed = True
    while changed:
        changed = False

        for block in reachable_blocks:
            if block == entry:
                continue

            if block.preds:
                new_dom = dominators[block.preds[0]].copy()

                for pred in (x for x in block.preds[1:] if x in reachable_blocks):
                    new_dom = new_dom.intersection(dominators[pred])

                new_dom.add(block)
            else:
                new_dom = {block}

            if new_dom != dominators[block]:
                changed = True
                dominators[block] = new_dom

    return dominators


def _build_dominator_tree(
    dominators: dict[BasicBlock, set[BasicBlock]], entry: BasicBlock
) -> DominatorTree:
    idom: dict[BasicBlock, Optional[BasicBlock]] = {}

    idom[entry] = None
    for block in dominators:
        if block == entry:
            continue

        doms = dominators[block] - {block}
        if not doms:
            idom[block] = None
            continue

        candidate_idom = None
        max_dom_count = -1
        for candidate in doms:
            dom_count = len(dominators[candidate])
            if dom_count > max_dom_count:
                max_dom_count = dom_count
                candidate_idom = candidate

        assert candidate_idom is not None
        idom[block] = candidate_idom

    reversed_idom: dict[BasicBlock, list[BasicBlock]] = defaultdict(list)
    for child, dom in idom.items():
        if dom is None:
            continue
        reversed_idom[dom].append(child)

    tree = DominatorTree(entry, idom, reversed_idom, dominators)
    return tree


def compute_dominance_frontier_graph(
    cfg: CFG, idom_tree: DominatorTree
) -> dict[BasicBlock, set[BasicBlock]]:
    DF: dict[BasicBlock, set[BasicBlock]] = defaultdict(set)
    for node in cfg:
        for pred in node.preds:
            if pred in idom_tree.dominators[node]:
                continue

            DF[pred].add(node)
            d = idom_tree.idom[pred]
            assert d is not None

            while d != idom_tree.idom[node]:
                DF[d].add(node)
                d = idom_tree.idom[d]
                assert d is not None
    return DF
