from collections import defaultdict, deque
from typing import Optional, Iterable, override

from src.optimizations.base import OptimizationPass
from src.ir.cfg import (
    CFG,
    BasicBlock,
    InstArrayInit,
    InstAssign,
    InstGetArgument,
    Instruction,
    LoopInfo,
    OpLoad,
    Operation,
    OpBinary,
    OpUnary,
    OpCall,
    SSAValue,
    SSAVariable,
    SSAConstant,
)
from src.ir.dominance import DominatorTree, compute_dominator_tree
from src.ir.helpers import unwrap


class LICM(OptimizationPass):
    def __init__(self):
        self.cfg: Optional[CFG] = None
        self.dom_tree: Optional[DominatorTree] = None
        self.def_to_block: dict[tuple[str, int], BasicBlock] = {}
        self.uses: dict[tuple[str, int], set[tuple[str, int]]] = defaultdict(set)

    @override
    def run(self, cfg: CFG):
        self.cfg = cfg
        self.dom_tree = compute_dominator_tree(cfg)
        self._index_definitions(cfg)
        self._collect_loop_blocks(cfg)
        for loop in cfg.loops_info:
            self._hoist_loop(loop)

    def _index_definitions(self, cfg: CFG):
        self.def_to_block.clear()
        self.uses.clear()
        for bb in cfg:
            for phi in bb.phi_nodes.values():
                def_key = (phi.lhs.name, unwrap(phi.lhs.version))
                self.def_to_block[def_key] = bb
                for _, val in phi.rhs.items():
                    if isinstance(val, SSAVariable):
                        use_key = (val.name, unwrap(val.version))
                        self.uses[use_key].add(def_key)

            for inst in bb.instructions:
                match inst:
                    case InstGetArgument():
                        def_key = (inst.lhs.name, unwrap(inst.lhs.version))
                        self.def_to_block[def_key] = bb
                    case InstAssign():
                        def_key = (inst.lhs.name, unwrap(inst.lhs.version))
                        self.def_to_block[def_key] = bb
                        for operand in self._collect_operands(inst.rhs):
                            if isinstance(operand, SSAVariable):
                                use_key = (operand.name, unwrap(operand.version))
                                self.uses[use_key].add(def_key)
                    case InstArrayInit():
                        def_key = (inst.lhs.name, unwrap(inst.lhs.version))
                        self.def_to_block[def_key] = bb

    def _bfs_order_blocks(
        self, header: BasicBlock, loop_blocks: set[BasicBlock]
    ) -> Iterable[BasicBlock]:
        seen_blocks = set([])
        q = deque([header])
        while len(q) > 0:
            bb = q.popleft()
            if bb in seen_blocks:
                continue

            seen_blocks.add(bb)
            yield bb

            q.extend((s for s in bb.succ if s in loop_blocks and s not in seen_blocks))

    def _collect_loop_blocks(self, cfg: CFG):
        for loop_info in cfg.loops_info:
            q = [loop_info.tail]
            loop_blocks: set[BasicBlock] = set([loop_info.preheader])
            while len(q) > 0:
                bb = q.pop()
                if bb in loop_blocks:
                    continue
                loop_blocks.add(bb)
                q.extend((p for p in bb.preds if p not in loop_blocks))

            loop_blocks.remove(loop_info.preheader)
            loop_info.blocks = loop_blocks

    def _dominates(self, a: BasicBlock, b: BasicBlock) -> bool:
        assert self.dom_tree is not None
        doms = self.dom_tree.dominators[b]
        return a in doms

    def _hoist_loop(self, loop: LoopInfo):
        assert self.dom_tree is not None

        preheader = loop.preheader
        invariant_defs = self._defs_outside_loop(loop.blocks)
        hoisted: list[InstAssign] = []

        changed = True
        while changed:
            changed = False
            for bb in self._bfs_order_blocks(loop.header, loop.blocks):
                new_insts: list[Instruction] = []
                for inst in bb.instructions:
                    if not self._is_hoistable(
                        inst, bb, loop.blocks, loop.tail, invariant_defs
                    ):
                        new_insts.append(inst)
                        continue

                    assert isinstance(inst, InstAssign)
                    hoisted.append(inst)

                    invariant_defs.add((inst.lhs.name, unwrap(inst.lhs.version)))
                    self.def_to_block[(inst.lhs.name, unwrap(inst.lhs.version))] = (
                        preheader
                    )
                    changed = True
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
        tail_block: BasicBlock,
        invariant_defs: set[tuple[str, int]],
    ) -> bool:
        if not isinstance(inst, InstAssign):
            return False

        rhs = inst.rhs
        if isinstance(rhs, OpCall) or isinstance(rhs, OpLoad):
            return False

        if not self._dominates(inst_block, tail_block):
            return False

        def_key = (inst.lhs.name, unwrap(inst.lhs.version))
        uses = self.uses.get(def_key, set())
        for use_def_key in uses:
            use_block = self.def_to_block.get(use_def_key)
            if use_block is None:
                continue
            if use_block in loop_blocks:
                if not self._dominates(inst_block, use_block):
                    return False

        return all(
            self._operand_is_invariant(op, loop_blocks, invariant_defs)
            for op in self._collect_operands(rhs)
        )

    def _collect_operands(self, rhs: Operation | SSAValue) -> Iterable[SSAValue]:
        if isinstance(rhs, Operation):
            match rhs:
                case OpLoad(addr):
                    return [addr]
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
            key = (operand.name, unwrap(operand.version))
            if key in invariant_defs:
                return True
            def_block = self.def_to_block[key]
            return def_block not in loop_blocks
        return False
