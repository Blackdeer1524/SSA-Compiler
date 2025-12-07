from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Literal, Optional, Iterable

from src.ssa.cfg import (
    CFG,
    BasicBlock,
    InstArrayInit,
    InstStore,
    InstUncondJump,
    Instruction,
    InstAssign,
    InstCmp,
    InstGetArgument,
    InstPhi,
    InstReturn,
    OpLoad,
    Operation,
    OpBinary,
    OpUnary,
    OpCall,
    SSAValue,
    SSAVariable,
    SSAConstant,
)


@dataclass(frozen=True)
class LatticeValue:
    kind: Literal["UNDEF", "CONST", "NAC"]
    value: Optional[int] = None

    @staticmethod
    def undef() -> "LatticeValue":
        return LatticeValue("UNDEF", None)

    @staticmethod
    def const(v: int) -> "LatticeValue":
        return LatticeValue("CONST", v)

    @staticmethod
    def nac() -> "LatticeValue":
        return LatticeValue("NAC", None)

    def is_undef(self) -> bool:
        return self.kind == "UNDEF"

    def is_const(self) -> bool:
        return self.kind == "CONST"

    def is_nac(self) -> bool:
        return self.kind == "NAC"


def join(a: LatticeValue, b: LatticeValue) -> LatticeValue:
    if a.kind == "UNDEF":
        return b
    if b.kind == "UNDEF":
        return a
    if a.kind == "NAC" or b.kind == "NAC":
        return LatticeValue.nac()
    # both CONST
    assert a.kind == "CONST" and b.kind == "CONST"
    return a if a.value == b.value else LatticeValue.nac()


class SCCP:
    def __init__(self):
        self.cfg: Optional[CFG] = None

        self.value_state: dict[tuple[str, int], LatticeValue] = {}
        self.executable_blocks: set[BasicBlock] = set()
        self.feasible_edges: set[tuple[BasicBlock, BasicBlock]] = set()

        self.block_worklist: deque[BasicBlock] = deque()
        self.var_worklist: deque[tuple[str, int]] = deque()

        self.uses: dict[tuple[str, int], set[Instruction | InstPhi]] = defaultdict(set)
        self.defs: dict[tuple[str, int], Instruction | InstPhi] = {}
        self.inst_block: dict[Instruction | InstPhi, BasicBlock] = {}

    def run(self, cfg: CFG):
        self.cfg = cfg
        self._build_metadata(cfg)

        # Initialization: entry block is executable
        self._mark_block_executable(cfg.entry)

        # Propagation loop
        while self.block_worklist or self.var_worklist:
            while self.block_worklist:
                bb = self.block_worklist.popleft()
                self._process_block(bb)

            while self.var_worklist:
                var_key = self.var_worklist.popleft()
                self._process_variable_users(var_key)

        # Rewrite CFG and fold constants
        self._rewrite_cfg()
        self._fold_constants()

    def _build_metadata(self, cfg: CFG):
        for bb in cfg:
            # Phi nodes first
            for phi in bb.phi_nodes.values():
                self.inst_block[phi] = bb
                # LHS def
                if phi.lhs.version is not None:
                    self.defs[(phi.lhs.name, phi.lhs.version)] = phi
                # RHS uses
                for pred_label, val in phi.rhs.items():
                    if isinstance(val, SSAVariable) and val.version is not None:
                        self.uses[(val.name, val.version)].add(phi)

            # Instructions
            for inst in bb.instructions:
                self.inst_block[inst] = bb
                match inst:
                    case InstAssign(lhs, rhs):
                        if lhs.version is not None:
                            self.defs[(lhs.name, lhs.version)] = inst
                        for v in self._iter_uses_from_rhs(rhs):
                            self.uses[v].add(inst)
                    case InstCmp(left, right):
                        for v in self._iter_uses_from_vals([left, right]):
                            self.uses[v].add(inst)
                    case InstReturn(value):
                        if value is not None:
                            for v in self._iter_uses_from_vals([value]):
                                self.uses[v].add(inst)
                    case InstStore(addr, value):
                        for v in self._iter_uses_from_vals([addr]):
                            self.uses[v].add(inst)
                        for v in self._iter_uses_from_rhs(value):
                            self.uses[v].add(inst)
                    case InstArrayInit(lhs):
                        if lhs.version is not None:
                            self.defs[(lhs.name, lhs.version)] = inst
                    case InstGetArgument(lhs, _):
                        if lhs.version is not None:
                            self.defs[(lhs.name, lhs.version)] = inst
                    case _:
                        pass

    def _iter_uses_from_rhs(
        self, rhs: Operation | SSAValue
    ) -> Iterable[tuple[str, int]]:
        if isinstance(rhs, Operation):
            match rhs:
                case OpLoad(addr):
                    yield from self._iter_uses_from_vals([addr])
                case OpBinary(_, left, right):
                    yield from self._iter_uses_from_vals([left, right])
                case OpUnary(_, val):
                    yield from self._iter_uses_from_vals([val])
                case OpCall(_, args):
                    yield from self._iter_uses_from_vals(args)
        else:
            yield from self._iter_uses_from_vals([rhs])

    def _iter_uses_from_vals(
        self, vals: Iterable[SSAValue]
    ) -> Iterable[tuple[str, int]]:
        for v in vals:
            if isinstance(v, SSAVariable) and v.version is not None:
                yield (v.name, v.version)

    def _mark_block_executable(self, bb: BasicBlock):
        if bb not in self.executable_blocks:
            self.executable_blocks.add(bb)
            self.block_worklist.append(bb)

    def _mark_edge_feasible(self, pred: BasicBlock, succ: BasicBlock):
        if (pred, succ) in self.feasible_edges:
            return
        self.feasible_edges.add((pred, succ))
        # First time succ gets any feasible edge => executable
        if succ not in self.executable_blocks:
            self._mark_block_executable(succ)
        # Update phis in successor
        self._update_phis_for_edge(pred, succ)

    def _update_phis_for_edge(self, pred: BasicBlock, succ: BasicBlock):
        for phi in succ.phi_nodes.values():
            # Consider only executable predecessors
            self._evaluate_phi(phi)

    def _get_lattice_of_value(self, v: SSAValue) -> LatticeValue:
        if isinstance(v, SSAConstant):
            return LatticeValue.const(v.value)
        if isinstance(v, SSAVariable):
            if v.version is None:
                return LatticeValue.undef()
            return self.value_state.get((v.name, v.version), LatticeValue.undef())
        return LatticeValue.nac()

    def _set_lattice(self, key: tuple[str, int], val: LatticeValue):
        old = self.value_state.get(key, LatticeValue.undef())
        new = join(old, val)
        if new != old:
            self.value_state[key] = new
            self.var_worklist.append(key)

    def _process_block(self, bb: BasicBlock):
        for phi in bb.phi_nodes.values():
            self._evaluate_phi(phi)

        for inst in bb.instructions:
            match inst:
                case InstAssign(_, _):
                    self._evaluate_assign(inst)
                case InstCmp(_, _):
                    self._evaluate_branch(inst, bb)
                case InstUncondJump(target):
                    self._mark_edge_feasible(bb, target)
                case InstArrayInit(_, _):
                    self._evaluate_array_init(inst)
                case InstGetArgument(_, _):
                    self._evaluate_get_argument(inst)
                case InstStore(_, _):
                    self._evaluate_store(inst)
                case _:
                    pass

    def _process_variable_users(self, key: tuple[str, int]):
        for user in self.uses.get(key, []):
            match user:
                case InstPhi():
                    bb = self.inst_block[user]
                    if bb in self.executable_blocks:
                        self._evaluate_phi(user)
                case InstAssign():
                    self._evaluate_assign(user)
                case InstCmp():
                    bb = self.inst_block[user]
                    if bb in self.executable_blocks:
                        self._evaluate_branch(user, bb)
                case InstStore():
                    self._evaluate_store(user)
                case _:
                    pass

    def _evaluate_phi(self, phi: InstPhi):
        # join over executable predecessors only
        vals: list[LatticeValue] = []
        succ_block = self.inst_block[phi]
        for pred in succ_block.preds:
            if (pred, succ_block) not in self.feasible_edges:
                continue
            # Must have incoming mapping for pred label
            incoming = phi.rhs.get(pred.label)
            if incoming is None:
                continue
            vals.append(self._get_lattice_of_value(incoming))

        result = LatticeValue.undef()
        for v in vals:
            result = join(result, v)

        assert phi.lhs.version is not None
        self._set_lattice((phi.lhs.name, phi.lhs.version), result)

    def _evaluate_assign(self, inst: InstAssign):
        lhs = inst.lhs
        val_lv = self._evaluate_rhs(inst.rhs)

        assert lhs.version is not None
        self._set_lattice((lhs.name, lhs.version), val_lv)

    def _evaluate_rhs(self, rhs: Operation | SSAValue) -> LatticeValue:
        if isinstance(rhs, Operation):
            match rhs:
                case OpLoad():
                    return LatticeValue.nac()
                case OpBinary(op, left, right):
                    lv = self._get_lattice_of_value(left)
                    rv = self._get_lattice_of_value(right)
                    return self._eval_binary(op, lv, rv)
                case OpUnary(op, val):
                    vv = self._get_lattice_of_value(val)
                    return self._eval_unary(op, vv)
                case OpCall(_, _):
                    # Unknown side-effects and results - not a constant
                    return LatticeValue.nac()
        else:
            return self._get_lattice_of_value(rhs)
        return LatticeValue.nac()

    def _evaluate_array_init(self, inst: InstArrayInit):
        lhs = inst.lhs
        assert lhs.version is not None
        self._set_lattice((lhs.name, lhs.version), LatticeValue.nac())

    def _evaluate_get_argument(self, inst: InstGetArgument):
        lhs = inst.lhs
        assert lhs.version is not None
        self._set_lattice((lhs.name, lhs.version), LatticeValue.nac())

    def _evaluate_store(self, inst: InstStore):
        return LatticeValue.nac()

    def _truthy(self, v: int) -> int:
        return 1 if v != 0 else 0

    def _eval_binary(self, op: str, a: LatticeValue, b: LatticeValue) -> LatticeValue:
        if a.is_nac() or b.is_nac():
            return LatticeValue.nac()
        if not (a.is_const() and b.is_const()):
            return LatticeValue.undef()
        x, y = a.value, b.value
        assert x is not None and y is not None
        try:
            if op == "+":
                return LatticeValue.const(x + y)
            if op == "-":
                return LatticeValue.const(x - y)
            if op == "*":
                return LatticeValue.const(x * y)
            if op == "/":
                if y == 0:
                    return LatticeValue.nac()
                return LatticeValue.const(x // y)
            if op == "%":
                if y == 0:
                    return LatticeValue.nac()
                return LatticeValue.const(x % y)
            if op == "==":
                return LatticeValue.const(1 if x == y else 0)
            if op == "!=":
                return LatticeValue.const(1 if x != y else 0)
            if op == "<":
                return LatticeValue.const(1 if x < y else 0)
            if op == "<=":
                return LatticeValue.const(1 if x <= y else 0)
            if op == ">":
                return LatticeValue.const(1 if x > y else 0)
            if op == ">=":
                return LatticeValue.const(1 if x >= y else 0)
            if op == "&&":
                return LatticeValue.const(self._truthy(x) & self._truthy(y))
            if op == "||":
                return LatticeValue.const(
                    1 if (self._truthy(x) | self._truthy(y)) else 0
                )
        except Exception:
            return LatticeValue.nac()
        return LatticeValue.nac()

    def _eval_unary(self, op: str, v: LatticeValue) -> LatticeValue:
        if v.is_nac():
            return LatticeValue.nac()
        if not v.is_const():
            return LatticeValue.undef()
        x = v.value
        assert x is not None
        try:
            if op == "-":
                return LatticeValue.const(-x)
            if op == "!":
                return LatticeValue.const(0 if x != 0 else 1)
        except Exception:
            return LatticeValue.nac()
        return LatticeValue.nac()

    def _evaluate_branch(self, br: InstCmp, bb: BasicBlock):
        left = br.left
        right = br.right
        lv = self._get_lattice_of_value(left)
        rv = self._get_lattice_of_value(right)
        if lv.is_const() and rv.is_const():
            cond_true = 1 if lv.value == rv.value else 0
            if cond_true == 1:
                self._mark_edge_feasible(bb, br.then_block)
            else:
                self._mark_edge_feasible(bb, br.else_block)
        elif lv.is_nac() or rv.is_nac():
            self._mark_edge_feasible(bb, br.then_block)
            self._mark_edge_feasible(bb, br.else_block)
        else:
            return

    def _rewrite_cfg(self):
        assert self.cfg is not None

        for bb in list(self.cfg):
            if bb in self.executable_blocks:
                continue

            for pred in bb.preds:
                pred.succ.remove(bb)

            for succ in bb.succ:
                succ.preds.remove(bb)
                for phi in succ.phi_nodes.values():
                    phi.rhs.pop(bb.label, None)

            bb.succ = []
            bb.preds = []

    def _fold_constants(self):
        assert self.cfg is not None

        for bb in self.cfg:
            pred_labels = set(pred.label for pred in bb.preds)
            for phi_node in bb.phi_nodes.values():
                new_rhs = {
                    pred: self._replace_in_rhs(val)
                    for pred, val in phi_node.rhs.items()
                    if pred in pred_labels
                }
                phi_node.rhs = new_rhs

            for i, inst in enumerate(bb.instructions):
                match inst:
                    case InstAssign(lhs, rhs):
                        new_rhs = self._replace_in_rhs(rhs)
                        # If operation now constant, collapse
                        if isinstance(new_rhs, Operation):
                            match new_rhs:
                                case OpBinary():
                                    lv = self._get_lattice_of_value(new_rhs.left)
                                    rv = self._get_lattice_of_value(new_rhs.right)
                                    folded = self._eval_binary(new_rhs.type, lv, rv)
                                    if folded.is_const():
                                        inst.rhs = SSAConstant(folded.value or 0)
                                    else:
                                        inst.rhs = new_rhs
                                case OpUnary():
                                    vv = self._get_lattice_of_value(new_rhs.val)
                                    folded = self._eval_unary(new_rhs.type, vv)
                                    if folded.is_const():
                                        inst.rhs = SSAConstant(folded.value or 0)
                                    else:
                                        inst.rhs = new_rhs
                                case _:
                                    inst.rhs = new_rhs
                        else:
                            inst.rhs = new_rhs
                    case InstCmp(left, right):
                        new_left = self._replace_value(left)
                        new_right = self._replace_value(right)
                        inst.left = new_left
                        inst.right = new_right

                        left_lattice = self._get_lattice_of_value(new_left)
                        right_lattice = self._get_lattice_of_value(new_right)

                        if left_lattice.is_const() and right_lattice.is_const():
                            if left_lattice.value == right_lattice.value:
                                bb.instructions[i] = InstUncondJump(inst.then_block)
                                for s in bb.succ:
                                    if s.label != inst.then_block.label:
                                        s.preds.remove(bb)
                                bb.succ = [inst.then_block]
                            else:
                                bb.instructions[i] = InstUncondJump(inst.else_block)
                                for s in bb.succ:
                                    if s.label != inst.else_block.label:
                                        s.preds.remove(bb)
                                bb.succ = [inst.else_block]
                    case InstReturn(value):
                        if value is not None:
                            inst.value = self._replace_value(value)
                    case _:
                        pass

    def _replace_in_rhs(self, rhs: Operation | SSAValue) -> Operation | SSAValue:
        if isinstance(rhs, Operation):
            match rhs:
                case OpBinary(op, left, right):
                    return OpBinary(
                        op, self._replace_value(left), self._replace_value(right)
                    )
                case OpUnary(op, val):
                    return OpUnary(op, self._replace_value(val))
                case OpCall(name, args):
                    return OpCall(name, tuple(self._replace_value(a) for a in args))
        else:
            return self._replace_value(rhs)
        return rhs

    def _replace_value(self, v: SSAValue) -> SSAValue:
        if isinstance(v, SSAVariable) and v.version is not None:
            lv = self.value_state.get((v.name, v.version))
            if lv is not None and lv.is_const():
                return SSAConstant(lv.value or 0)
        return v
