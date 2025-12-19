from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
import re
import textwrap
from typing import Iterator, Optional, Sequence
from src.parsing.parser import (
    Program,
    Function,
    Statement,
    Assignment,
    Reassignment,
    Condition,
    ForLoop,
    UnconditionalLoop,
    FunctionCall,
    Return,
    Break,
    Continue,
    Block,
    Expression,
    BinaryOp,
    UnaryOp,
    Identifier,
    IntegerLiteral,
    CallExpression,
    ArrayAccess,
    ArrayInit,
    LValueIdentifier,
    LValueArrayAccess,
)
from src.parsing.semantic import SymbolTable
from src.ssa.helpers import bb_colors, color_label, unwrap


@dataclass
class SSAValue(ABC): ...


@dataclass
class SSAVariable(SSAValue):
    name: str
    base_pointer: Optional[tuple[str, int]] = field(default=None, compare=False)
    version: int | None = field(default=None)

    def __repr__(self):
        res = ""
        if self.base_pointer is not None:
            if (
                self.base_pointer[0] == self.name
                and self.base_pointer[1] == self.version
            ):
                res += "(<~)"
            else:
                res += f"({self.base_pointer[0]}_v{self.base_pointer[1]}<~)"

        res += self.name
        if self.version is not None:
            res += f"_v{self.version}"
        return res

    def as_tuple(self):
        return (self.name, unwrap(self.version))


@dataclass
class SSAConstant(SSAValue):
    value: int

    def __repr__(self):
        return str(self.value)


class Operation(ABC): ...


@dataclass
class OpCall(Operation):
    name: str
    args: Sequence["SSAValue"]

    def __repr__(self):
        args_str = ", ".join(repr(arg) for arg in self.args)
        return f"{self.name}({args_str})"


@dataclass
class OpBinary(Operation):
    type: str
    left: "SSAValue"
    right: "SSAValue"

    def __repr__(self):
        return f"{self.left} {self.type} {self.right}"


@dataclass
class OpLoad(Operation):
    addr: "SSAVariable"

    def __repr__(self):
        return f"Load({self.addr})"


@dataclass
class OpUnary(Operation):
    type: str
    val: "SSAValue"

    def __repr__(self):
        return f"{self.type}{self.val}"


@dataclass(eq=False)
class Instruction(ABC):
    @abstractmethod
    def to_IR(self) -> str: ...


@dataclass(eq=False)
class InstAssign(Instruction):
    lhs: SSAVariable
    rhs: Operation | SSAValue

    def to_IR(self):
        return f"{self.lhs} = {self.rhs}"


@dataclass(eq=False)
class InstCmp(Instruction):
    left: SSAValue
    right: SSAValue

    then_block: "BasicBlock"
    else_block: "BasicBlock"

    def to_IR(self):
        ir = f"cmp({self.left}, {self.right})\n"
        ir += f"if CF == 1 then jmp {self.then_block.label} else jmp {self.else_block.label}"
        return ir


@dataclass(eq=False)
class InstUncondJump(Instruction):
    target_block: "BasicBlock"

    def to_IR(self):
        return f"jmp {self.target_block.label}"


@dataclass(eq=False)
class InstReturn(Instruction):
    value: Optional[SSAValue]

    def to_IR(self):
        if self.value is None:
            return "return"
        return f"return({self.value})"


@dataclass(eq=False)
class InstPhi(Instruction):
    lhs: "SSAVariable"
    rhs: dict[str, "SSAValue"]  # Basic Block name -> corresponding SSAValue

    def to_IR(self):
        rhs_str = ", ".join(f"{bb}: {val}" for bb, val in self.rhs.items())
        return f"{self.lhs} = ϕ({rhs_str})"


@dataclass(eq=False)
class InstArrayInit(Instruction):
    lhs: SSAVariable
    dimensions: list[int]

    def to_IR(self):
        dims_str = "".join(f"[{d}]" for d in self.dimensions)
        return f"{self.lhs} = array_init({dims_str})"


@dataclass(eq=False)
class InstStore(Instruction):
    dst_address: SSAVariable
    value: SSAValue

    def to_IR(self):
        return f"Store({self.dst_address}, {self.value})"


@dataclass(eq=False)
class InstGetArgument(Instruction):
    lhs: SSAVariable
    index: int

    def to_IR(self):
        return f"{self.lhs} = getarg({self.index})"


class BasicBlock:
    def __init__(
        self, label: str, symbol_table: SymbolTable, meta: Optional[str] = None
    ):
        self.label = label
        self.meta = meta

        self.symbol_table: SymbolTable = symbol_table

        self.instructions: list[Instruction] = []
        self.phi_nodes: dict[str, InstPhi] = {}
        self.preds: list["BasicBlock"] = []
        self.succ: list["BasicBlock"] = []

    def insert_phi(self, name: str):
        if self.phi_nodes.get(name) is None:
            self.phi_nodes[name] = InstPhi(SSAVariable(name), {})

    def append(self, inst: Instruction):
        self.instructions.append(inst)

    def add_child(self, bb: "BasicBlock"):
        if bb not in self.succ:
            self.succ.append(bb)
        if self not in bb.preds:
            bb.preds.append(self)

    def add_pred(self, bb: "BasicBlock"):
        if bb not in self.preds:
            self.preds.append(bb)
        if self not in bb.succ:
            bb.succ.append(self)

    def __hash__(self):
        return hash(self.label)

    def __repr__(self):
        return self.label

    def to_IR(self) -> str:
        self.symbol_table

        res = ""
        res += f"; pred: {self.preds}\n"
        res += self.label + ":"
        if self.meta is not None:
            res += f" ; [{self.meta}]"
        res += "\n"

        if len(self.phi_nodes) > 0:
            for phi in self.phi_nodes.values():
                res += "    " + phi.to_IR().replace("\n", "\n    ") + "\n"
            res += "\n"

        for inst in self.instructions:
            res += "    " + inst.to_IR().replace("\n", "\n    ") + "\n"

        res += f"; succ: {self.succ}"
        return res

    def to_html(self):
        res = ""
        res += f'<font color="grey">; pred: {[color_label(bb.label) for bb in self.preds]}</font><br ALIGN="LEFT"/>'
        res += color_label(self.label) + ":"
        if self.meta is not None:
            res += f' <font color="grey">; [{self.meta}]</font>'
        res += '<br ALIGN="left"/>'

        if len(self.phi_nodes) > 0:
            for phi in self.phi_nodes.values():
                res += re.sub(
                    r"(BB\d+)",
                    lambda x: color_label(x[0]),
                    "    "
                    + phi.to_IR().replace("\n", '<br ALIGN="left"/>    ')
                    + '<br ALIGN="left"/>',
                )

            res += '<br ALIGN="left"/>'

        for inst in self.instructions:
            res += "    " + (
                re.sub(
                    r"(BB\d+)",
                    lambda x: color_label(x[0]),
                    inst.to_IR()
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                    .replace("\n", '<br ALIGN="left"/>    ')
                    + '<br ALIGN="left"/>',
                )
            )

        res += f'<font color="grey">; succ: {[color_label(bb.label) for bb in self.succ]}</font>'
        res += '<br ALIGN="left"/>'
        return res


@dataclass
class CFG:
    """Control Flow Graph for a function."""

    name: str
    entry: BasicBlock
    exit: BasicBlock

    def bfs(self) -> Iterator[tuple[int, BasicBlock]]:
        visited_blocks = set()
        q = deque([(0, self.entry)])
        while len(q) > 0:
            (depth, bb) = q.popleft()
            if bb in visited_blocks:
                continue
            visited_blocks.add(bb)
            yield (depth, bb)
            q.extend(((depth + 1, s) for s in bb.succ if s not in visited_blocks))

    def __iter__(self) -> Iterator[BasicBlock]:
        visited_blocks = set()
        q = [self.entry]
        while len(q) > 0:
            n = q.pop()
            if n in visited_blocks:
                continue
            visited_blocks.add(n)
            yield n
            q.extend((s for s in n.succ if s not in visited_blocks))

    def to_graphviz(
        self,
        src: str,
        reversed_idom_tree: dict[BasicBlock, list[BasicBlock]],
        dominance_frontier: dict["BasicBlock", set["BasicBlock"]],
    ):
        res = f"digraph {self.name} {{\n"
        res += "rankdir = TD;\n"

        block_src_code = (
            textwrap.dedent(src)
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", '<br ALIGN="left"/>')
            + '<br ALIGN="left"/>'
        )
        source_block = f'"src" [label=<{block_src_code}>]'
        res += f"""
            subgraph cluster_source_code {{
                node [shape=box]
                label="Исходный код";
            {source_block}
            }}
            
            subgraph cluster_original {{
                label="Граф потока управления";
        """

        res += "node [shape=box]\n"

        for bb in self:
            bb_repr = bb.to_html().replace("\\l", '<br ALIGN="LEFT"/>')
            res += f'"{bb.label}" [label=<{bb_repr}>]\n'

        for bb in self:
            for succ in bb.succ:
                res += (
                    f'"{bb.label}" -> "{succ.label}" '
                    + '[headport="n", tailport="s", penwidth=3, '
                    + f'color="{bb_colors[succ.label]};0.5:{bb_colors[bb.label]}"]\n'
                )

        for parent, children in reversed_idom_tree.items():
            for child in children:
                res += f'"{parent.label}" -> "{child.label}" [color=blue]\n'

        for bb, dfs in dominance_frontier.items():
            for df in dfs:
                res += f'"{bb.label}" -> "{df.label}" [color=red]\n'

        res += "}"
        res += "}"
        return res

    def to_IR(self) -> str:
        res = ""
        for bb in self:
            res += bb.to_IR()
            res += "\n\n"
        return res


class CFGBuilder:
    def __init__(self):
        self.block_counter = 0
        self.tmp_var_counter = 0
        self.cur_block: Optional[BasicBlock] = None
        self.break_targets: list[BasicBlock] = []  # Stack of break targets
        self.continue_targets: list[BasicBlock] = []  # Stack of continue targets

    def _get_tmp_var(self) -> str:
        name = f"%{self.tmp_var_counter}"
        self.tmp_var_counter += 1
        return name

    def _new_block(
        self, symbol_table: SymbolTable, meta: Optional[str] = None
    ) -> BasicBlock:
        name = f"BB{self.block_counter}"
        self.block_counter += 1
        bb = BasicBlock(name, symbol_table, meta)
        return bb

    def _switch_to_block(self, bb: BasicBlock):
        self.cur_block = bb

    def build(self, program: Program) -> list[CFG]:
        cfgs = []
        for func in program.functions:
            cfg = self._build_function(func)
            cfgs.append(cfg)
        return cfgs

    def _build_function(self, func: Function) -> CFG:
        self.break_targets = []
        self.continue_targets = []

        assert func.body.symbol_table is not None
        entry = self._new_block(func.body.symbol_table, "entry")
        exit_block = self._new_block(func.body.symbol_table, "exit")

        self.current_cfg = CFG(func.name, entry=entry, exit=exit_block)
        self.cur_block = entry

        for i, arg in enumerate(func.args):
            self.cur_block.append(InstGetArgument(SSAVariable(arg.name), i))
        self._build_block(func.body)

        if not self.cur_block.succ:
            self.cur_block.add_child(exit_block)

        return self.current_cfg

    def _build_block(self, syntax_block: Block):
        assert self.cur_block is not None

        for stmt in syntax_block.statements:
            self._build_statement(stmt)

    def _build_statement(self, stmt: Statement):
        match stmt:
            case Assignment():
                self._build_assignment(stmt)
            case Reassignment():
                self._build_reassignment(stmt)
            case Condition():
                self._build_condition(stmt)
            case ForLoop():
                self._build_for_loop(stmt)
            case UnconditionalLoop():
                self._build_unconditional_loop(stmt)
            case FunctionCall():
                self._build_function_call(stmt)
            case Return():
                self._build_return(stmt)
            case Break():
                self._build_break(stmt)
            case Continue():
                self._build_continue(stmt)

    def _build_assignment(self, stmt: Assignment):
        assert self.cur_block is not None, "Current block must be set"

        type_info = unwrap(self.cur_block.symbol_table.lookup_variable(stmt.name))
        if isinstance(stmt.value, ArrayInit):
            lhs_var = SSAVariable(stmt.name)
            self.cur_block.append(InstArrayInit(lhs_var, type_info.dimensions))
            return

        subexpr_ssa_val = self._build_subexpression(stmt.value, stmt.name)
        if (
            not isinstance(subexpr_ssa_val, SSAVariable)
            or subexpr_ssa_val.name != stmt.name
        ):
            lhs = SSAVariable(stmt.name)
            self.cur_block.append(InstAssign(lhs, subexpr_ssa_val))

    def _build_subexpression(self, expr: Expression, name: str) -> SSAValue:
        assert self.cur_block is not None, "Current block must be set"

        match expr:
            case BinaryOp(_, _, op, left, right):
                left_val = self._build_subexpression(left, self._get_tmp_var())
                right_val = self._build_subexpression(right, self._get_tmp_var())

                lhs = SSAVariable(name)
                self.cur_block.append(
                    InstAssign(lhs, OpBinary(op, left_val, right_val))
                )
                return lhs
            case UnaryOp(_, _, op, operand):
                subexpr_val = self._build_subexpression(operand, self._get_tmp_var())
                lhs = SSAVariable(name)
                self.cur_block.append(InstAssign(lhs, OpUnary(op, subexpr_val)))
                return lhs
            case Identifier(_, _, ident_name):
                return SSAVariable(ident_name)
            case IntegerLiteral(_, _, value):
                return SSAConstant(value)
            case CallExpression(_, _, func_name, args):
                args = [
                    self._build_subexpression(arg, self._get_tmp_var()) for arg in args
                ]
                lhs = SSAVariable(name)
                self.cur_block.append(InstAssign(lhs, OpCall(func_name, args)))
                return lhs
            case ArrayAccess():
                return self._build_array_access(expr, name)
            case ArrayInit():
                return SSAVariable(name)
            case _:
                raise ValueError(f"Unknown expression type: {type(expr).__name__}")

    def _build_array_access(self, expr: ArrayAccess, name: str) -> SSAValue:
        """Build array access with pointer arithmetic and dereference."""
        assert self.cur_block is not None, "Current block must be set"

        base_val = self._build_subexpression(expr.base, self._get_tmp_var())

        assert isinstance(expr.base, Identifier)
        array_type = unwrap(self.cur_block.symbol_table.lookup_variable(expr.base.name))
        assert array_type.is_array()

        dimensions = array_type.dimensions
        strides = []
        for i in range(len(dimensions)):
            # Stride for dimension i is the product of all dimensions after i
            stride = 1
            for j in range(i + 1, len(dimensions)):
                stride *= dimensions[j]
            strides.append(stride)

        current_addr: Optional[SSAVariable] = None

        for i, index_expr in enumerate(expr.indices):
            index_val = self._build_subexpression(index_expr, self._get_tmp_var())

            stride_const = SSAConstant(strides[i])
            stride_tmp = SSAVariable(self._get_tmp_var())
            stride_op = OpBinary("*", index_val, stride_const)
            self.cur_block.append(InstAssign(stride_tmp, stride_op))

            if current_addr is None:
                current_addr = stride_tmp
            else:
                addr_tmp = SSAVariable(self._get_tmp_var())
                op = OpBinary("+", current_addr, stride_tmp)
                self.cur_block.append(InstAssign(addr_tmp, op))
                current_addr = addr_tmp

        if current_addr is None:
            addr_tmp = SSAVariable(self._get_tmp_var())
            self.cur_block.append(InstAssign(addr_tmp, base_val))
            current_addr = addr_tmp
        else:
            addr_tmp = SSAVariable(self._get_tmp_var())
            op = OpBinary("+", base_val, current_addr)
            self.cur_block.append(InstAssign(addr_tmp, op))
            current_addr = addr_tmp

        assert isinstance(current_addr, SSAVariable)
        lhs = SSAVariable(name)
        self.cur_block.append(InstAssign(lhs, OpLoad(current_addr)))
        return lhs

    def _build_reassignment(self, stmt: Reassignment):
        assert self.cur_block is not None, "Current block must be set"

        if isinstance(stmt.lvalue, LValueArrayAccess):
            self._build_array_element_assignment(stmt.lvalue, stmt.value)
            return

        assert isinstance(stmt.lvalue, LValueIdentifier), (
            "Expected LValueIdentifier for simple reassignment"
        )
        subexpr_ssa_val = self._build_subexpression(stmt.value, stmt.lvalue.name)
        if (
            not isinstance(subexpr_ssa_val, SSAVariable)
            or subexpr_ssa_val.name != stmt.lvalue.name
        ):
            lhs = SSAVariable(stmt.lvalue.name)
            self.cur_block.append(InstAssign(lhs, subexpr_ssa_val))

    def _build_array_element_assignment(
        self, lvalue: LValueArrayAccess, value: Expression
    ):
        """Build array element assignment: arr[i][j] = value."""
        assert self.cur_block is not None, "Current block must be set"

        array_type = unwrap(self.cur_block.symbol_table.lookup_variable(lvalue.base))
        assert array_type.is_array()

        dimensions = array_type.dimensions
        strides = []
        for i in range(len(dimensions)):
            # Stride for dimension i is the product of all dimensions after i
            stride = 1
            for j in range(i + 1, len(dimensions)):
                stride *= dimensions[j]
            strides.append(stride)

        base_val = SSAVariable(lvalue.base)
        current_addr: Optional[SSAVariable] = None

        for i, index_expr in enumerate(lvalue.indices):
            index_val = self._build_subexpression(index_expr, self._get_tmp_var())

            stride_const = SSAConstant(strides[i])
            stride_tmp = SSAVariable(self._get_tmp_var())
            stride_op = OpBinary("*", index_val, stride_const)
            self.cur_block.append(InstAssign(stride_tmp, stride_op))

            if current_addr is None:
                current_addr = stride_tmp
            else:
                addr_tmp = SSAVariable(self._get_tmp_var())
                op = OpBinary("+", current_addr, stride_tmp)
                self.cur_block.append(InstAssign(addr_tmp, op))
                current_addr = addr_tmp

        if current_addr is None:
            addr_tmp = SSAVariable(self._get_tmp_var())
            self.cur_block.append(InstAssign(addr_tmp, base_val))
            current_addr = addr_tmp
        else:
            addr_tmp = SSAVariable(self._get_tmp_var())
            op = OpBinary("+", base_val, current_addr)
            self.cur_block.append(InstAssign(addr_tmp, op))
            current_addr = addr_tmp

        value_tmp = self._get_tmp_var()
        value_val = self._build_subexpression(value, value_tmp)
        self.cur_block.append(InstStore(current_addr, value_val))

    def _build_function_call(self, stmt: FunctionCall):
        assert self.cur_block is not None, "Current block must be set"
        tmp = SSAVariable(self._get_tmp_var())
        args = [
            self._build_subexpression(arg, self._get_tmp_var()) for arg in stmt.args
        ]
        self.cur_block.append(InstAssign(tmp, OpCall(stmt.name, args)))

    def _build_condition(self, stmt: Condition):
        assert self.cur_block is not None, "Current block must be set"

        then_block = self._new_block(unwrap(stmt.then_block.symbol_table), "then")
        merge_block = self._new_block(self.cur_block.symbol_table, "merge")

        cond_var = self._build_subexpression(stmt.condition, self._get_tmp_var())
        if stmt.else_block is None:
            self.cur_block.append(
                InstCmp(cond_var, SSAConstant(0), merge_block, then_block)
            )
            self.cur_block.add_child(merge_block)
        else:
            else_block = self._new_block(unwrap(stmt.else_block.symbol_table), "else")
            self.cur_block.append(
                InstCmp(cond_var, SSAConstant(0), else_block, then_block)
            )
            self.cur_block.add_child(else_block)

            old_block = self.cur_block
            self._switch_to_block(else_block)
            self._build_block(stmt.else_block)

            if len(self.cur_block.instructions) == 0 or not isinstance(
                self.cur_block.instructions[-1], (InstUncondJump, InstCmp, InstReturn)
            ):
                self.cur_block.add_child(merge_block)
                self.cur_block.append(InstUncondJump(merge_block))
                self._switch_to_block(old_block)

        self.cur_block.add_child(then_block)
        self._switch_to_block(then_block)
        self._build_block(stmt.then_block)

        if len(self.cur_block.instructions) == 0 or not isinstance(
            self.cur_block.instructions[-1], (InstUncondJump, InstCmp, InstReturn)
        ):
            self.cur_block.add_child(merge_block)
            self.cur_block.append(InstUncondJump(merge_block))

        self._switch_to_block(merge_block)

    def _build_for_loop(self, stmt: ForLoop):
        assert self.cur_block is not None, "Current block must be set"

        body_st = unwrap(stmt.body.symbol_table)
        initial_cond_block = self._new_block(body_st, "condition check")
        preheader_block = self._new_block(body_st, "loop preheader")
        body_block = self._new_block(body_st, "loop body")
        update_block = self._new_block(body_st, "loop update")

        # required for an easier loop detection in LICM : all tail's predecessors are guaranteed to be loop blocks
        tail_block = self._new_block(body_st, "loop tail")
        exit_block = self._new_block(self.cur_block.symbol_table, "loop exit")

        self.cur_block.append(InstUncondJump(initial_cond_block))
        self.cur_block.add_child(initial_cond_block)
        self._switch_to_block(initial_cond_block)

        for assignment in stmt.init:
            self._build_assignment(assignment)
        cond_var = self._build_subexpression(stmt.condition, self._get_tmp_var())
        self.cur_block.append(
            InstCmp(cond_var, SSAConstant(0), exit_block, preheader_block)
        )
        self.cur_block.add_child(preheader_block)
        self.cur_block.add_child(exit_block)

        self._switch_to_block(preheader_block)
        self.cur_block.append(InstUncondJump(body_block))
        self.cur_block.add_child(body_block)

        self.break_targets.append(tail_block)
        self.continue_targets.append(update_block)
        self._switch_to_block(body_block)
        self._build_block(stmt.body)

        if len(self.cur_block.instructions) == 0 or not isinstance(
            self.cur_block.instructions[-1], (InstUncondJump, InstCmp, InstReturn)
        ):
            self.cur_block.add_child(update_block)
            self.cur_block.append(InstUncondJump(update_block))

        self._switch_to_block(update_block)
        for reassignment in stmt.update:
            self._build_reassignment(reassignment)
        cond_var2 = self._build_subexpression(stmt.condition, self._get_tmp_var())
        self.cur_block.append(
            InstCmp(cond_var2, SSAConstant(0), tail_block, body_block)
        )
        self.cur_block.add_child(body_block)
        self.cur_block.add_child(tail_block)

        self.break_targets.pop()
        self.continue_targets.pop()

        self._switch_to_block(tail_block)
        self.cur_block.append(InstUncondJump(exit_block))
        self.cur_block.add_child(exit_block)

        self._switch_to_block(exit_block)

    def _build_unconditional_loop(self, stmt: UnconditionalLoop):
        assert self.cur_block is not None, "Current block must be set"

        body_st = unwrap(stmt.body.symbol_table)
        preheader_block = self._new_block(body_st, "uncond loop preheader")
        body_block = self._new_block(body_st, "uncond loop body")
        update_block = self._new_block(body_st, "uncond loop update")
        tail_block = self._new_block(body_st, "uncond loop tail")
        exit_block = self._new_block(self.cur_block.symbol_table, "uncond loop exit")

        self.cur_block.append(InstUncondJump(preheader_block))
        self.cur_block.add_child(preheader_block)
        self._switch_to_block(preheader_block)

        self.cur_block.append(InstUncondJump(body_block))
        self.cur_block.add_child(body_block)
        self._switch_to_block(body_block)

        self.break_targets.append(tail_block)
        self.continue_targets.append(update_block)
        self._build_block(stmt.body)
        self.break_targets.pop()
        self.continue_targets.pop()

        if len(self.cur_block.instructions) == 0 or not isinstance(
            self.cur_block.instructions[-1], (InstUncondJump, InstCmp, InstReturn)
        ):
            self.cur_block.add_child(update_block)
            self.cur_block.append(InstUncondJump(update_block))

        self._switch_to_block(update_block)
        self.cur_block.append(InstUncondJump(body_block))
        self.cur_block.add_child(body_block)

        self._switch_to_block(tail_block)
        self.cur_block.append(InstUncondJump(exit_block))
        self.cur_block.add_child(exit_block)

        self._switch_to_block(exit_block)

    def _build_return(self, stmt: Return):
        assert self.cur_block is not None, "Current block must be set"
        assert self.current_cfg is not None, "Current CFG must be set"

        if stmt.value is not None:
            ret_ssa = self._build_subexpression(stmt.value, self._get_tmp_var())
            self.cur_block.append(InstReturn(ret_ssa))
        else:
            self.cur_block.append(InstReturn(None))

        self.cur_block.add_child(self.current_cfg.exit)
        self._switch_to_block(
            self._new_block(self.cur_block.symbol_table, "after return")
        )

    def _build_break(self, _: Break):
        assert self.cur_block is not None, "Current block must be set"

        assert self.break_targets
        if self.break_targets:
            target = self.break_targets[-1]
            self.cur_block.add_child(target)
            self.cur_block.append(InstUncondJump(target))

    def _build_continue(self, _: Continue):
        assert self.cur_block is not None, "Current block must be set"

        if self.continue_targets:
            target = self.continue_targets[-1]
            self.cur_block.add_child(target)
            self.cur_block.append(InstUncondJump(target))
