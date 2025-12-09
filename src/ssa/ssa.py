from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Optional
from src.ssa.cfg import (
    CFG,
    BasicBlock,
    InstArrayInit,
    InstAssign,
    InstCmp,
    InstGetArgument,
    InstPhi,
    InstReturn,
    InstStore,
    Instruction,
    OpBinary,
    OpCall,
    OpLoad,
    OpUnary,
    Operation,
    SSAValue,
    SSAVariable,
)
from src.ssa.dominance import compute_dominance_frontier_graph, compute_dominator_tree
from src.ssa.helpers import unwrap


@dataclass
class DefInfo:
    defining_blocks: set[BasicBlock] = field(init=False, default_factory=set)

    def add(self, bb: BasicBlock):
        self.defining_blocks.add(bb)


class SSABuilder:
    def __init__(self): ...

    def _compute_liveness(self):
        block_ud: dict[BasicBlock, tuple[set[str], set[str]]] = {}
        self.live_in: dict[BasicBlock, set[str]] = {}
        self.live_out: dict[BasicBlock, set[str]] = {}
        for bb in self.cfg:
            block_ud[bb] = self._collect_uses_defs(bb)
            self.live_in[bb] = set()
            self.live_out[bb] = set()

        changed = True
        while changed:
            changed = False
            for bb in self.cfg:
                uses, defs = block_ud[bb]
                new_out: set[str] = set()
                for succ in bb.succ:
                    new_out |= self.live_in[succ]
                new_in = uses | (new_out - defs)
                if new_out != self.live_out[bb] or new_in != self.live_in[bb]:
                    self.live_out[bb] = new_out
                    self.live_in[bb] = new_in
                    changed = True

    def _collect_uses_defs(self, bb: BasicBlock) -> tuple[set[str], set[str]]:
        uses: set[str] = set()
        defs: set[str] = set()

        def use_val(val: SSAValue):
            if isinstance(val, SSAVariable) and val.name not in defs:
                uses.add(val.name)

        for inst in bb.instructions:
            match inst:
                case InstAssign(lhs, rhs):
                    # uses from RHS
                    if isinstance(rhs, Operation):
                        match rhs:
                            case OpLoad(addr):
                                use_val(addr)
                            case OpBinary(_, left, right):
                                use_val(left)
                                use_val(right)
                            case OpUnary(_, val):
                                use_val(val)
                            case OpCall(_, args):
                                for a in args:
                                    use_val(a)
                    else:
                        use_val(rhs)
                    defs.add(lhs.name)
                case InstCmp(left, right):
                    use_val(left)
                    use_val(right)
                case InstReturn(val):
                    if val is not None:
                        use_val(val)
                case InstArrayInit(lhs):
                    defs.add(lhs.name)
                case InstStore(addr, rhs):
                    uses.add(addr.name)
                    use_val(rhs)
                case InstGetArgument(lhs, _):
                    defs.add(lhs.name)
                case _:
                    pass
        return uses, defs

    def _put_phis(self):
        defs_by_var: dict[str, DefInfo] = defaultdict(DefInfo)
        for bb in self.idom_tree.traverse():
            for inst in bb.instructions:
                if isinstance(inst, (InstAssign, InstGetArgument, InstArrayInit)):
                    defs_by_var[inst.lhs.name].add(bb)

        for var, def_blocks in defs_by_var.items():
            has_phi: set[BasicBlock] = set()
            work: list[BasicBlock] = list(def_blocks.defining_blocks)
            while work:
                n = work.pop()
                for y in self.DF[n]:
                    if y in has_phi:
                        continue

                    if var not in self.live_in[y]:
                        continue  # prune

                    y.insert_phi(var)
                    has_phi.add(y)
                    if not any(
                        isinstance(i, (InstAssign, InstGetArgument, InstArrayInit))
                        and i.lhs.name == var
                        for i in y.instructions
                    ):
                        work.append(y)

    def _rename_inst(self, inst: Instruction, bb: BasicBlock) -> Optional[str]:
        match inst:
            case InstAssign(lhs, rhs):
                match rhs:
                    case Operation():
                        self._rename_operation(rhs)
                    case SSAVariable():
                        self._rename_var(rhs)
                self._new_version(lhs, inst, bb)
                return lhs.name
            case InstPhi(lhs, rhs):
                self._new_version(lhs, inst, bb)
                return lhs.name
            case InstCmp(left, right):
                self._rename_ssa_val(left)
                self._rename_ssa_val(right)
            case InstReturn(val):
                if val is None:
                    return
                self._rename_ssa_val(val)
            case InstArrayInit(lhs):
                self._new_version(lhs, inst, bb)
                return lhs.name
            case InstStore(addr, val):
                self._rename_ssa_val(addr)
                self._rename_ssa_val(val)
            case InstGetArgument(lhs, _):
                self._new_version(lhs, inst, bb)
                return lhs.name

    def _rename_ssa_val(self, val: SSAValue):
        if isinstance(val, SSAVariable):
            self._rename_var(val)

    def _rename_operation(self, op: Operation):
        match op:
            case OpLoad(addr):
                self._rename_ssa_val(addr)
            case OpCall():
                for arg in op.args:
                    self._rename_ssa_val(arg)
            case OpBinary():
                self._rename_ssa_val(op.left)
                self._rename_ssa_val(op.right)
            case OpUnary():
                self._rename_ssa_val(op.val)

    def _rename_var(self, var: SSAVariable):
        assert len(self.versions[var.name]) > 0, var.name

        var.version = self.versions[var.name][-1]
        if (base_ptr := self.ptr_info.get(var.name)) is not None:
            var.base_pointer = base_ptr

    def _new_version(self, var: SSAVariable, inst: Instruction, bb: BasicBlock):
        def iter_vars_from_rhs(rhs: Operation | SSAValue) -> Iterable[SSAVariable]:
            def iter_vars_from_vals(vals: Iterable[SSAValue]) -> Iterable[SSAVariable]:
                for v in vals:
                    if isinstance(v, SSAVariable) and v.version is not None:
                        yield v

            if isinstance(rhs, Operation):
                match rhs:
                    case OpBinary(_, left, right):
                        yield from iter_vars_from_vals([left, right])
                    case OpUnary(_, val):
                        yield from iter_vars_from_vals([val])
            else:
                yield from iter_vars_from_vals([rhs])

        self.version_counter[var.name] += 1
        var.version = self.version_counter[var.name]
        self.versions[var.name].append(var.version)

        type_info = bb.symbol_table.lookup_variable(var.name)
        if type_info is None:
            match inst:
                case InstAssign():
                    for v in iter_vars_from_rhs(inst.rhs):
                        if v.base_pointer is None:
                            continue
                        var.base_pointer = v.base_pointer
                        break
                case InstPhi():
                    for v in inst.rhs.values():
                        if not isinstance(v, SSAVariable) or v.base_pointer is None:
                            continue
                        var.base_pointer = v.base_pointer
                        break

        elif type_info.is_array():
            self.ptr_info[var.name] = (var.name, var.version)
            var.base_pointer = (var.name, var.version)

    def _rename_helper(self, bb: BasicBlock):
        block_new_assign_count: dict[str, int] = defaultdict(lambda: 0)

        for phi_inst in bb.phi_nodes.values():
            var = unwrap(self._rename_inst(phi_inst, bb))
            block_new_assign_count[var] += 1

        for inst in bb.instructions:
            var = self._rename_inst(inst, bb)
            if var is not None:
                block_new_assign_count[var] += 1

        for succ in bb.succ:
            for phi_var, phi_inst in succ.phi_nodes.items():
                if self.versions.get(phi_var) is None:
                    continue
                version = self.versions[phi_var][-1]
                phi_inst.rhs[bb.label] = SSAVariable(
                    phi_var, phi_inst.lhs.base_pointer, version
                )

        for child in self.idom_tree.reversed_idom[bb]:
            self._rename_helper(child)

        for var, c in block_new_assign_count.items():
            self.versions[var] = self.versions[var][:-c]

    def _insert_get_argument_instructions(self):
        entry = self.cfg.entry
        for i, arg in enumerate(self.cfg.args):
            lhs = SSAVariable(arg.name)
            entry.instructions.append(InstGetArgument(lhs, i))

    def build(self, cfg: CFG):
        self.cfg = cfg
        self.idom_tree = compute_dominator_tree(cfg)
        self.DF = compute_dominance_frontier_graph(cfg, self.idom_tree)

        self.ptr_info: dict[str, tuple[str, int]] = {}
        self.versions: dict[str, list[int]] = defaultdict(lambda: [])
        self.version_counter: dict[str, int] = defaultdict(lambda: 0)

        self._insert_get_argument_instructions()
        self._compute_liveness()
        self._put_phis()
        self._rename_helper(cfg.entry)
