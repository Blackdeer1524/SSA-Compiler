from collections import defaultdict, deque
from typing import Iterable, Optional

from src.ssa.cfg import (
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
    SSAValue,
    SSAVariable,
)


class DCE:
    def __init__(self):
        self.cfg: Optional[CFG] = None
        # Def-use
        self.defs: dict[tuple[str, int], Instruction | InstPhi] = {}
        self.uses: dict[tuple[str, int], set[Instruction | InstPhi]] = defaultdict(set)
        self.inst_block: dict[Instruction | InstPhi, BasicBlock] = {}
        # Liveness
        self.live_insts: set[Instruction | InstPhi] = set()
        self.live_vars: set[tuple[str, int]] = set()

    def run(self, cfg: CFG):
        self.cfg = cfg
        self._build_metadata(cfg)
        self._mark_and_sweep(cfg)
        self._rewrite(cfg)

    def _build_metadata(self, cfg: CFG):
        for bb in cfg:
            # Phis
            for phi in bb.phi_nodes.values():
                self.inst_block[phi] = bb
                assert phi.lhs.version is not None
                self.defs[(phi.lhs.name, phi.lhs.version)] = phi

                for _, v in phi.rhs.items():
                    if isinstance(v, SSAVariable) and v.version is not None:
                        self.uses[(v.name, v.version)].add(phi)

            # Instructions
            for inst in bb.instructions:
                self.inst_block[inst] = bb
                match inst:
                    case InstArrayInit(lhs):
                        if lhs.version is not None:
                            self.defs[(lhs.name, lhs.version)] = inst
                    case InstAssign(lhs, rhs):
                        if lhs.version is not None:
                            self.defs[(lhs.name, lhs.version)] = inst
                        for use_key in self._iter_uses_from_rhs(rhs):
                            self.uses[use_key].add(inst)
                    case InstGetArgument(lhs, _):
                        if lhs.version is not None:
                            self.defs[(lhs.name, lhs.version)] = inst
                    case InstCmp(left=left, right=right):
                        for use_key in self._iter_uses_from_vals([left, right]):  # type: ignore[name-defined]
                            self.uses[use_key].add(inst)
                    case InstReturn(value):
                        if value is not None:
                            for use_key in self._iter_uses_from_vals([value]):
                                self.uses[use_key].add(inst)
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

    # ---------- Liveness ----------
    def _seed_roots(self, cfg: CFG, var_work: deque[tuple[str, int]]):
        for inst in (inst for bb in cfg for inst in bb.instructions):
            match inst:
                case InstStore(addr, value):
                    self.live_insts.add(inst)
                    if isinstance(value, SSAVariable) and value.version is not None:
                        key = (value.name, value.version)
                        if key not in self.live_vars:
                            self.live_vars.add(key)
                            var_work.append(key)
                case InstAssign(lhs, rhs):
                    if isinstance(rhs, OpCall):
                        # Treat calls as side-effectful roots
                        self.live_insts.add(inst)
                        for arg in rhs.args:
                            if isinstance(arg, SSAVariable) and arg.version is not None:
                                key = (arg.name, arg.version)
                                if key not in self.live_vars:
                                    self.live_vars.add(key)
                                    var_work.append(key)
                case InstReturn(value):
                    self.live_insts.add(inst)
                    if isinstance(value, SSAVariable) and value.version is not None:
                        key = (value.name, value.version)
                        if key not in self.live_vars:
                            self.live_vars.add(key)
                            var_work.append(key)
                case InstCmp(left=left, right=right):
                    # Terminator: always live; seed operands
                    self.live_insts.add(inst)
                    for key in self._iter_uses_from_vals([left, right]):
                        if key not in self.live_vars:
                            self.live_vars.add(key)
                            var_work.append(key)
                case _:
                    pass

    def _mark_and_sweep(self, cfg: CFG):
        var_work: deque[tuple[str, int]] = deque()
        self._seed_roots(cfg, var_work)

        while var_work:
            key = var_work.popleft()
            defining_inst = self.defs[key]
            if defining_inst in self.live_insts:
                continue

            self.live_insts.add(defining_inst)
            match defining_inst:
                case InstAssign(lhs, rhs):
                    for op_key in self._iter_uses_from_rhs(rhs):
                        if op_key not in self.live_vars:
                            self.live_vars.add(op_key)
                            var_work.append(op_key)
                case InstPhi(lhs, rhs):
                    for _, v in rhs.items():
                        if isinstance(v, SSAVariable) and v.version is not None:
                            vkey = (v.name, v.version)
                            if vkey not in self.live_vars:
                                self.live_vars.add(vkey)
                                var_work.append(vkey)
                case _:
                    pass

    # ---------- Rewriting ----------
    def _rewrite(self, cfg: CFG):
        # Remove dead PHI nodes
        for bb in cfg:
            to_remove = []
            for name, phi in bb.phi_nodes.items():
                if phi not in self.live_insts:
                    to_remove.append(name)
            for name in to_remove:
                bb.phi_nodes.pop(name, None)

        # Remove dead instructions
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
                    case _:
                        new_insts.append(inst)
            bb.instructions = new_insts
