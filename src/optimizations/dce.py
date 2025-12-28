from collections import defaultdict, deque
from typing import Iterable, Optional, override

from src.optimizations.base import OptimizationPass
from src.ir.cfg import (
    CFG,
    BasicBlock,
    InstArrayInit,
    InstStore,
    Instruction,
    InstAssign,
    InstCmp,
    InstGetArgument,
    InstUncondJump,
    InstReturn,
    InstPhi,
    OpLoad,
    Operation,
    OpBinary,
    OpUnary,
    OpCall,
    SSAConstant,
    SSAValue,
    SSAVariable,
)
from src.ir.helpers import unwrap


class DCE(OptimizationPass):
    def __init__(self):
        self.cfg: Optional[CFG] = None
        # Def-use
        self.defs: dict[tuple[str, int], tuple[Instruction | InstPhi, int]] = {}
        self.uses: dict[tuple[str, int], set[Instruction | InstPhi]] = defaultdict(set)
        self.inst_block: dict[Instruction | InstPhi, BasicBlock] = {}
        # Liveness
        self.live_insts: set[Instruction | InstPhi] = set()
        self.live_vars: set[tuple[str, int]] = set()

    @override
    def run(self, cfg: CFG):
        self.cfg = cfg
        self._build_metadata(cfg)
        self._mark(cfg)
        self._sweep(cfg)

    def _build_metadata(self, cfg: CFG):
        for bb in cfg:
            # Phis
            for phi in bb.phi_nodes.values():
                self.inst_block[phi] = bb
                assert phi.lhs.version is not None
                self.defs[(phi.lhs.name, phi.lhs.version)] = (phi, -1)

                for _, v in phi.rhs.items():
                    if isinstance(v, SSAVariable) and v.version is not None:
                        self.uses[(v.name, v.version)].add(phi)

            # Instructions
            for i, inst in enumerate(bb.instructions):
                self.inst_block[inst] = bb
                match inst:
                    case InstArrayInit(lhs):
                        self.defs[(lhs.name, unwrap(lhs.version))] = (inst, i)
                    case InstAssign(lhs, rhs):
                        self.defs[(lhs.name, unwrap(lhs.version))] = (inst, i)
                        for use_key in self._iter_ssavars(rhs):
                            self.uses[(use_key.name, unwrap(use_key.version))].add(inst)
                    case InstGetArgument(lhs, _):
                        self.defs[(lhs.name, unwrap(lhs.version))] = (inst, i)
                    case InstCmp(left=left, right=right):
                        for use_key in self._iter_uses_from_vals([left, right]):  # type: ignore[name-defined]
                            self.uses[(use_key.name, unwrap(use_key.version))].add(inst)
                    case InstReturn(value):
                        if value is not None:
                            for use_key in self._iter_uses_from_vals([value]):
                                self.uses[(use_key.name, unwrap(use_key.version))].add(
                                    inst
                                )
                    case _:
                        pass

    def _iter_ssavars(self, rhs: Operation | SSAValue) -> Iterable[SSAVariable]:
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

    def _iter_uses_from_vals(self, vals: Iterable[SSAValue]) -> Iterable[SSAVariable]:
        for v in vals:
            if isinstance(v, SSAVariable):
                assert v.version is not None
                yield v

    def _mark_pointer_chain(
        self,
        bb: BasicBlock,
        ptr_seed: SSAVariable,
        seed_idx: int,
        var_work: deque[tuple[str, int]],
    ):
        for inst in reversed(bb.instructions[:seed_idx]):
            if not isinstance(inst, InstStore):
                continue
            if inst.dst_address.base_pointer != ptr_seed.base_pointer:
                continue

            key = (inst.dst_address.name, unwrap(inst.dst_address.version))
            if key in self.live_vars:
                return

            self.live_vars.add(key)
            var_work.append(key)
            self.live_insts.add(inst)

        q = [pred for pred in bb.preds if pred != bb]
        seen: set[BasicBlock] = set()  # do NOT include bb
        while len(q) > 0:
            cur = q.pop()
            if cur in seen:
                continue
            seen.add(cur)

            dead_end = False
            for inst in cur.instructions[::-1]:
                if not isinstance(inst, InstStore):
                    continue

                if inst.dst_address.base_pointer != ptr_seed.base_pointer:
                    continue

                if inst in self.live_insts:
                    dead_end = True
                    break

                key = (inst.dst_address.name, unwrap(inst.dst_address.version))
                self.live_insts.add(inst)
                if key not in self.live_vars:
                    self.live_vars.add(key)
                    var_work.append(key)

                if isinstance(inst.value, SSAVariable):
                    key = (inst.value.name, unwrap(inst.value.version))
                    if key not in self.live_vars:
                        self.live_vars.add(key)
                        var_work.append(key)

            if not dead_end:
                q.extend((pred for pred in cur.preds if pred not in seen))

    def mark_value_live(
        self,
        bb: BasicBlock,
        inst_idx: int,
        val: SSAValue,
        var_work: deque[tuple[str, int]],
    ):
        if not isinstance(val, SSAVariable):
            return

        key = (val.name, unwrap(val.version))
        if val.base_pointer is not None:
            self._mark_pointer_chain(bb, val, inst_idx, var_work)

        if key in self.live_vars:
            return

        self.live_vars.add(key)
        var_work.append(key)

    def _seed_roots(self, cfg: CFG, var_work: deque[tuple[str, int]]):
        for bb in cfg:
            for i, inst in enumerate(bb.instructions):
                match inst:
                    case InstGetArgument(lhs):
                        if lhs.base_pointer is not None:
                            k = (lhs.name, unwrap(lhs.version))
                            self.live_vars.add(k)
                            self.live_insts.add(inst)
                            self._mark_pointer_chain(cfg.exit, lhs, -1, var_work)
                    case InstAssign(_, rhs):
                        match rhs:
                            case OpBinary("/" | "%", _, SSAVariable() | SSAConstant(0)):
                                # division-by-zero or modulo zero, which is side-effectful -> can't remove
                                self.live_insts.add(inst)
                                self.mark_value_live(bb, i, rhs.left, var_work)
                                self.mark_value_live(bb, i, rhs.right, var_work)
                            case OpCall():
                                # Treat calls as side-effectful roots
                                self.live_insts.add(inst)
                                for arg in rhs.args:
                                    self.mark_value_live(bb, i, arg, var_work)
                    case InstReturn(value):
                        self.live_insts.add(inst)
                        if value is not None:
                            self.mark_value_live(bb, i, value, var_work)
                    case InstCmp(left=left, right=right):
                        # Terminator: always live; seed operands
                        self.live_insts.add(inst)
                        self.mark_value_live(bb, i, left, var_work)
                        self.mark_value_live(bb, i, right, var_work)
                    case _:
                        pass

    def _mark(self, cfg: CFG):
        var_work: deque[tuple[str, int]] = deque()
        self._seed_roots(cfg, var_work)

        while var_work:
            key = var_work.popleft()
            def_inst, def_idx = self.defs[key]
            if def_inst in self.live_insts:
                continue

            bb = self.inst_block[def_inst]
            self.live_insts.add(def_inst)
            match def_inst:
                case InstGetArgument() | InstArrayInit():
                    # no right hand side => no new variables => skip
                    ...
                case InstAssign(_, rhs):
                    for op_key in self._iter_ssavars(rhs):
                        self.mark_value_live(bb, def_idx, op_key, var_work)
                case InstPhi(_, rhs):
                    for _, v in rhs.items():
                        self.mark_value_live(bb, def_idx, v, var_work)
                case _:
                    raise RuntimeError(
                        f"unexpected definition instruction type: {type(def_inst)}"
                    )

    # ---------- Rewriting ----------
    def _sweep(self, cfg: CFG):
        # Remove dead PHI nodes
        for bb in cfg:
            to_remove = []
            for name, phi in bb.phi_nodes.items():
                if phi not in self.live_insts:
                    to_remove.append(name)
            for name in to_remove:
                bb.phi_nodes.pop(name, None)

        for bb in cfg:
            new_insts: list[Instruction] = []
            for inst in bb.instructions:
                match inst:
                    case InstUncondJump(_):
                        new_insts.append(inst)
                    case InstReturn(_):
                        new_insts.append(inst)
                    case InstCmp():
                        new_insts.append(inst)
                    case InstAssign(_, _):
                        if inst in self.live_insts:
                            new_insts.append(inst)
                    case InstGetArgument(_, _):
                        if inst in self.live_insts:
                            new_insts.append(inst)
                    case InstArrayInit(_, _):
                        if inst in self.live_insts:
                            new_insts.append(inst)
                    case InstStore():
                        if inst in self.live_insts:
                            new_insts.append(inst)
                    case _:
                        raise RuntimeError(f"unexpeted instruction type: {type(inst)}")
            bb.instructions = new_insts
