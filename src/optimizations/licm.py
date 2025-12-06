from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Optional, Iterable

from src.ssa.cfg import (
    CFG,
    BasicBlock,
    InstAssign,
    Instruction,
    Operation,
    OpBinary,
    OpUnary,
    OpCall,
    SSAValue,
    SSAVariable,
    SSAConstant,
)
from src.ssa.dominance import DominatorTree, compute_dominator_tree


@dataclass
class LoopInfo:
    header: BasicBlock
    preheader: BasicBlock
    blocks: set[BasicBlock]
    exit_block: BasicBlock


class LICM:
    def __init__(self):
        self.cfg: Optional[CFG] = None
        self.dom_tree: Optional[DominatorTree] = None
        self.def_to_block: dict[tuple[str, int], BasicBlock] = {}
        self.uses: dict[tuple[str, int], set[tuple[str, int]]] = defaultdict(set)

    def run(self, cfg: CFG):
        self.cfg = cfg
        self.dom_tree = compute_dominator_tree(cfg)
        self._index_definitions(cfg)
        loops = self._find_loops(cfg)
        for loop in sorted(loops, key=lambda x: len(x.blocks)):
            self._hoist_loop(loop)

    def _index_definitions(self, cfg: CFG):
        self.def_to_block.clear()
        self.uses.clear()
        for bb in cfg:
            for phi in bb.phi_nodes.values():
                if phi.lhs.version is not None:
                    def_key = (phi.lhs.name, phi.lhs.version)
                    self.def_to_block[def_key] = bb
                    for _, val in phi.rhs.items():
                        if isinstance(val, SSAVariable) and val.version is not None:
                            use_key = (val.name, val.version)
                            self.uses[use_key].add(def_key)

            for inst in bb.instructions:
                if isinstance(inst, InstAssign) and inst.lhs.version is not None:
                    def_key = (inst.lhs.name, inst.lhs.version)
                    self.def_to_block[def_key] = bb
                    for operand in self._collect_operands(inst.rhs):
                        if (
                            isinstance(operand, SSAVariable)
                            and operand.version is not None
                        ):
                            use_key = (operand.name, operand.version)
                            self.uses[use_key].add(def_key)

    def _find_loops(self, cfg: CFG) -> list[LoopInfo]:
        assert self.dom_tree is not None
        loops: list[LoopInfo] = []
        for bb in cfg:
            for succ in bb.succ:
                if not self._dominates(succ, bb):
                    continue

                assert len(bb.succ) == 2  # one back edge and one forward edge

                loop_blocks = self._collect_loop_blocks(header=succ, tail=bb)
                preheaders = [pred for pred in succ.preds if pred not in loop_blocks]
                assert len(preheaders) == 1

                loops.append(
                    LoopInfo(
                        header=succ,
                        preheader=preheaders[0],
                        blocks=loop_blocks,
                        exit_block=bb.succ[0] if bb.succ[0] != succ else bb.succ[1],
                    )
                )

        return loops

    def _dominates(self, a: BasicBlock, b: BasicBlock) -> bool:
        assert self.dom_tree is not None
        doms = self.dom_tree.dominators.get(b)
        if doms is None:
            return False
        return a in doms

    def _collect_loop_blocks(
        self, header: BasicBlock, tail: BasicBlock
    ) -> set[BasicBlock]:
        seen_loop_blocks = {header}
        stack = [tail]
        while stack:
            node = stack.pop()
            if node in seen_loop_blocks:
                continue
            seen_loop_blocks.add(node)
            stack.extend(node.preds)
        return seen_loop_blocks

    def _hoist_loop(self, loop: LoopInfo):
        assert self.dom_tree is not None

        preheader = loop.preheader
        invariant_defs = self._defs_outside_loop(loop.blocks)
        hoisted: list[InstAssign] = []

        changed = True
        while changed:
            changed = False
            for bb in self.dom_tree.traverse(loop.header):
                if bb not in loop.blocks:
                    continue

                new_insts: list[Instruction] = []
                for inst in bb.instructions:
                    if self._is_hoistable(
                        inst, bb, loop.blocks, loop.exit_block, invariant_defs
                    ):
                        assert isinstance(inst, InstAssign)
                        hoisted.append(inst)

                        assert inst.lhs.version is not None
                        invariant_defs.add((inst.lhs.name, inst.lhs.version))
                        self.def_to_block[(inst.lhs.name, inst.lhs.version)] = preheader
                        changed = True
                    else:
                        new_insts.append(inst)
                bb.instructions = new_insts

        if not hoisted:
            return

        preheader_jmp_inst = preheader.instructions.pop()
        preheader.instructions.extend(hoisted)
        preheader.instructions.append(preheader_jmp_inst)

    def _defs_outside_loop(self, loop_blocks: set[BasicBlock]) -> set[tuple[str, int]]:
        res: set[tuple[str, int]] = set()
        for key, block in self.def_to_block.items():
            if block not in loop_blocks:
                res.add(key)
        return res

    def _is_hoistable(
        self,
        inst: Instruction,
        inst_block: BasicBlock,
        loop_blocks: set[BasicBlock],
        exit_block: BasicBlock,
        invariant_defs: set[tuple[str, int]],
    ) -> bool:
        if not isinstance(inst, InstAssign):
            return False

        rhs = inst.rhs
        if isinstance(rhs, OpCall):
            return False  # potential side effects -> no hoisting

        if not self._dominates(inst_block, exit_block):
            return False

        assert inst.lhs.version is not None
        def_key = (inst.lhs.name, inst.lhs.version)
        uses = self.uses.get(def_key, set())
        for use_def_key in uses:
            use_block = self.def_to_block.get(use_def_key)
            if use_block is None:
                continue
            if use_block in loop_blocks:
                if not self._dominates(inst_block, use_block):
                    return False

        operands = list(self._collect_operands(rhs))
        if not operands:
            return True

        return all(
            self._operand_is_invariant(op, loop_blocks, invariant_defs)
            for op in operands
        )

    def _collect_operands(self, rhs: Operation | SSAValue) -> Iterable[SSAValue]:
        if isinstance(rhs, Operation):
            match rhs:
                case OpBinary(_, left, right):
                    return [left, right]
                case OpUnary(_, val):
                    return [val]
                case OpCall(_, args):
                    return list(args)
        else:
            return [rhs]
        return []

    def _operand_is_invariant(
        self,
        operand: SSAValue,
        loop_blocks: set[BasicBlock],
        invariant_defs: set[tuple[str, int]],
    ) -> bool:
        if isinstance(operand, SSAConstant):
            return True
        if isinstance(operand, SSAVariable):
            assert operand.version is not None
            key = (operand.name, operand.version)
            if key in invariant_defs:
                return True
            def_block = self.def_to_block.get(key)
            return def_block is not None and def_block not in loop_blocks
        return False
