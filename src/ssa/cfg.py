from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from tkinter import Entry
from typing import Iterable, Iterator, Optional, Sequence
from src.parsing.parser import (
    Program, Function, Statement, Assignment, Reassignment,
    Condition, ForLoop, UnconditionalLoop, FunctionCall, Return, Break, Continue, Block,
    Expression, BinaryOp, UnaryOp, Identifier, IntegerLiteral, CallExpression
)
from collections import deque, defaultdict

@dataclass
class SSAValue(ABC):
    ...

@dataclass
class SSAVariable(SSAValue): 
    name: str
    version: int | None = field(default=None)
    
    def __repr__(self):
        return self.name if self.version is None else f"{self.name}_v{self.version}"

@dataclass
class SSAConstant(SSAValue):
    value: int
    
    def __repr__(self):
        return str(self.value)

class Operation(ABC):
    ...

@dataclass
class OpCall(Operation): 
    name: str
    args: Sequence['SSAValue']
    
    def __repr__(self):
        args_str = ", ".join(repr(arg) for arg in self.args)
        return f"{self.name}({args_str})"

@dataclass
class OpBinary(Operation):
    type: str
    left: 'SSAValue'
    right: 'SSAValue'
    
    def __repr__(self):
        return f"{self.left} {self.type} {self.right}"

@dataclass
class OpUnary(Operation):
    type: str
    val: 'SSAValue'
    
    def __repr__(self):
        return f"{self.type}{self.val}"

@dataclass(eq=False)
class Instruction(ABC):
    @abstractmethod
    def to_IR(self) -> str:
        ...

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
    
    then_label: str
    else_label: str
    
    def to_IR(self):
        ir = f"cmp({self.left}, {self.right})\\n"
        ir += f"if CF == 1 then jmp {self.then_label} else jmp {self.else_label}"
        return ir

@dataclass(eq=False)
class InstUncondJump(Instruction):
    label: str
    
    def to_IR(self):
        return f"jmp {self.label}"


@dataclass(eq=False)
class InstReturn(Instruction):
    value: Optional[SSAValue]
    
    def to_IR(self):
        if self.value is None:
            return "return"
        return f"return({self.value})"
    

@dataclass(eq=False)
class InstPhi(Instruction):
    lhs: 'SSAVariable'
    rhs: dict[str, 'SSAValue']  # Basic Block name -> corresponding SSAValue
    
    def to_IR(self):
        rhs_str = ", ".join(f"{bb}: {val}" for bb, val in self.rhs.items())
        return f"{self.lhs} = ϕ({rhs_str})"


class BasicBlock:
    def __init__(self, label: str, meta: Optional[str] = None):
        self.label = label
        self.meta = meta

        self.instructions: list[Instruction] = []
        self.phi_nodes: dict[str, InstPhi] = {}
        self.preds: list['BasicBlock'] = []
        self.succ: list['BasicBlock'] = []

    def insert_phi(self, name: str):
        if self.phi_nodes.get(name) is None:
            self.phi_nodes[name] = InstPhi(SSAVariable(name), {})

    def append(self, inst: Instruction):
        self.instructions.append(inst)
    
    def add_child(self, bb: 'BasicBlock'):
        if bb not in self.succ:
            self.succ.append(bb)
        if self not in bb.preds:
            bb.preds.append(self)
    
    def add_pred(self, bb: 'BasicBlock'):
        if bb not in self.preds:
            self.preds.append(bb)
        if self not in bb.succ:
            bb.succ.append(self)
    
    def __hash__(self):
        return hash(self.label)
    
    def __repr__(self):
        return self.label
    
    def to_IR(self):
        label = f"preds: {self.preds}\n"
        label += self.label + ":"
        if self.meta is not None:
            label += f" [{self.meta}]"
        label += "\n\n"

        if len(self.phi_nodes) > 0:
            for phi in self.phi_nodes.values():
                label += '  ' + phi.to_IR() + '\n'
            label += '\n'
        
        for inst in self.instructions:
            label += '  ' + inst.to_IR() + '\n'

        label += "\n"
        label += f"succ: {self.succ}\n"
        return label
       
@dataclass
class CFG:
    """Control Flow Graph for a function."""
    name: str
    entry: BasicBlock
    exit: BasicBlock
    
    def traverse(self) -> Iterator[BasicBlock]:
        visited_blocks = set()
        q = [self.entry]
        while len(q) > 0:
            n = q.pop()
            visited_blocks.add(n)
            yield n
            q.extend((s for s in n.succ if s not in visited_blocks))
    
    def to_graphviz(self, reversed_idom_tree: dict[BasicBlock, list[BasicBlock]], dominance_frontier: dict["BasicBlock", set["BasicBlock"]]):
        res = f"digraph {self.name} {{\n"
        res += "node [shape=box]\n"

        # Render all nodes
        for bb in self.traverse():
            res += f'"{bb.label}" [label="{bb.to_IR()}"]\n'

        # Render CFG edges
        for bb in self.traverse():
            for succ in bb.succ:
                res += f'"{bb.label}" -> "{succ.label}"\n'

        # Render dominator tree edges in blue
        for parent, children in reversed_idom_tree.items():
            for child in children:
                res += f'"{parent.label}" -> "{child.label}" [color=blue]\n'

        # Render dominance frontier edges in red
        for bb, dfs in dominance_frontier.items():
            for df in dfs:
                res += f'"{bb.label}" -> "{df.label}" [color=red]\n'

        res += "}"
        return res

    def to_IR(self) -> str:
        res = ""
        for bb in self.traverse():
            res += bb.to_IR()
        return res

class CFGBuilder:
    def __init__(self):
        self.block_counter = 0
        self.tmp_var_counter = 0
        self.current_block: Optional[BasicBlock] = None
        self.break_targets: list[BasicBlock] = []  # Stack of break targets
        self.continue_targets: list[BasicBlock] = []  # Stack of continue targets
    
    def _get_tmp_var(self) -> SSAVariable:
        name = SSAVariable(f"%{self.tmp_var_counter}") 
        self.tmp_var_counter += 1
        return name
    
    def _new_block(self, meta: Optional[str] = None) -> BasicBlock:
        name = f"BB{self.block_counter}"
        self.block_counter += 1
        bb = BasicBlock(name, meta)
        return bb
    
    def _switch_to_block(self, bb: BasicBlock):
        self.current_block = bb
    
    def build(self, program: Program) -> list[CFG]:
        cfgs = []
        for func in program.functions:
            cfg = self._build_function(func)
            cfgs.append(cfg)
        return cfgs
    
    def _build_function(self, func: Function) -> CFG:
        self.block_counter = 0
        self.break_targets = []
        self.continue_targets = []
        
        entry = self._new_block("entry")
        exit_block = self._new_block("exit")
        
        cfg = CFG(func.name, entry=entry, exit=exit_block)
        self.current_cfg = cfg
        self.current_block = entry
        
        self._build_block(func.body)
        
        if not self.current_block.succ:
            self.current_block.add_child(exit_block)
        
        return cfg
    
    def _build_block(self, block: Block):
        for stmt in block.statements:
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
            case Block():
                self._build_block(stmt)
    
    def _build_assignment(self, stmt: Assignment):
        assert self.current_block is not None, "Current block must be set"
        
        lhs_var = SSAVariable(stmt.name)
        subexpr_ssa_val = self._build_subexpression(stmt.value, lhs_var)
        if subexpr_ssa_val != lhs_var:
            self.current_block.append(InstAssign(SSAVariable(stmt.name), subexpr_ssa_val))
    
    def _build_subexpression(self, expr: Expression, name: SSAVariable) -> SSAValue:
        assert self.current_block is not None, "Current block must be set"

        match expr:
            case BinaryOp(op, left, right):
                l = self._build_subexpression(left, self._get_tmp_var())
                r = self._build_subexpression(right, self._get_tmp_var())
                self.current_block.append(
                    InstAssign(name, OpBinary(op, l, r))
                )
                return name
            case UnaryOp(op, operand):
                subexpr_val = self._build_subexpression(operand, self._get_tmp_var())
                self.current_block.append(InstAssign(name, OpUnary(op, subexpr_val)))
                return name
            case Identifier(ident_name):
                return SSAVariable(ident_name)
            case IntegerLiteral(value):
                return SSAConstant(value)
            case CallExpression(func_name, args):
                args = [self._build_subexpression(arg, self._get_tmp_var()) for arg in args]
                self.current_block.append(InstAssign(name, OpCall(func_name, args)))
                return name
            case _:
                raise ValueError(f"Unknown expression type: {type(expr).__name__}")
    
    def _build_reassignment(self, stmt: Reassignment):
        assert self.current_block is not None, "Current block must be set"
        
        lhs_var = SSAVariable(stmt.name)
        subexpr_ssa_val = self._build_subexpression(stmt.value, lhs_var)
        if subexpr_ssa_val != lhs_var:
            self.current_block.append(InstAssign(SSAVariable(stmt.name), subexpr_ssa_val))
    
    def _build_function_call(self, stmt: FunctionCall):
        assert self.current_block is not None, "Current block must be set"
        tmp = self._get_tmp_var()
        args = [self._build_subexpression(arg, self._get_tmp_var()) for arg in stmt.args]
        self.current_block.append(InstAssign(tmp, OpCall(stmt.name, args)))
    
    def _build_condition(self, stmt: Condition):
        assert self.current_block is not None, "Current block must be set"
        
        then_block = self._new_block("then")
        merge_block = self._new_block("merge")
        
        cond_var = self._build_subexpression(stmt.condition, self._get_tmp_var())
        if stmt.else_block is None:
            self.current_block.append(InstCmp(cond_var, SSAConstant(1), then_block.label, merge_block.label))
            self.current_block.add_child(merge_block)
        else:
            else_block = self._new_block("else")
            self.current_block.append(InstCmp(cond_var, SSAConstant(1), then_block.label, else_block.label))
            self.current_block.add_child(else_block)

            old_block = self.current_block
            self._switch_to_block(else_block)
            self._build_block(stmt.else_block)

            if len(self.current_block.instructions) == 0 or not isinstance(self.current_block.instructions[-1], (InstUncondJump, InstCmp)):
                self.current_block.add_child(merge_block)
                self.current_block.append(InstUncondJump(merge_block.label))
                self._switch_to_block(old_block)

        self.current_block.add_child(then_block)
        self._switch_to_block(then_block)
        self._build_block(stmt.then_block)
        
        if len(self.current_block.instructions) == 0 or not isinstance(self.current_block.instructions[-1], (InstUncondJump, InstCmp)):
            self.current_block.add_child(merge_block)
            self.current_block.append(InstUncondJump(merge_block.label))

        self._switch_to_block(merge_block)
    
    def _build_for_loop(self, stmt: ForLoop):
        assert self.current_block is not None, "Current block must be set"
        
        init_block = self._new_block("loop init")
        header_block = self._new_block("loop header")
        exit_block = self._new_block("loop exit")

        body_block = self._new_block("loop body")
        update_block = self._new_block("loop update")
        
        self.break_targets.append(exit_block)
        self.continue_targets.append(update_block)
        
        self.current_block.add_child(init_block)
        self.current_block.append(InstUncondJump(init_block.label))

        self._switch_to_block(init_block) 
        self.current_block.add_child(header_block)
        self._build_assignment(stmt.init)
        self.current_block.append(InstUncondJump(header_block.label))

        self._switch_to_block(header_block)
        self.current_block.add_child(body_block) 
        self.current_block.add_child(exit_block)
        cond_var = self._build_subexpression(stmt.condition, self._get_tmp_var())
        self.current_block.append(InstCmp(cond_var, SSAConstant(1), body_block.label, exit_block.label))
        
        self._switch_to_block(body_block)
        self._build_block(stmt.body)
        
        if len(self.current_block.instructions) == 0 or not isinstance(self.current_block.instructions[-1], (InstUncondJump, InstCmp)):
            self.current_block.add_child(update_block)
            self.current_block.append(InstUncondJump(update_block.label))
        
        self._switch_to_block(update_block)
        self.current_block.add_child(header_block)
        self._build_reassignment(stmt.update)
        self.current_block.append(InstUncondJump(header_block.label))
        
        self.break_targets.pop()
        self.continue_targets.pop()
        self._switch_to_block(exit_block)
    
    def _build_unconditional_loop(self, stmt: UnconditionalLoop):
        assert self.current_block is not None, "Current block must be set"
        
        init_block = self._new_block("uncond loop init")
        body_block = self._new_block("uncond loop body")
        exit_block = self._new_block("uncond loop exit")
        
        self.break_targets.append(exit_block)
        self.continue_targets.append(init_block)
        
        self.current_block.add_child(init_block)
        self.current_block.append(InstUncondJump(init_block.label))
        
        self._switch_to_block(init_block)
        self.current_block.add_child(body_block)
        self.current_block.append(InstUncondJump(body_block.label))
        
        self._switch_to_block(body_block)
        self._build_block(stmt.body)
        
        self.current_block.add_child(init_block)
        self.current_block.append(InstUncondJump(body_block.label))
        
        self.break_targets.pop()
        self.continue_targets.pop()
        
        self._switch_to_block(exit_block)
    
    def _build_return(self, stmt: Return):
        assert self.current_block is not None, "Current block must be set"
        assert self.current_cfg is not None, "Current CFG must be set"

        if stmt.value is not None:
            ret_ssa = self._build_subexpression(stmt.value, self._get_tmp_var())
            self.current_block.append(InstReturn(ret_ssa))
        else:
            self.current_block.append(InstReturn(None))

        self.current_block.add_child(self.current_cfg.exit)
        self._switch_to_block(self._new_block("after return"))
    
    def _build_break(self, stmt: Break):
        assert self.current_block is not None, "Current block must be set"
        
        assert self.break_targets
        if self.break_targets:
            target = self.break_targets[-1]
            self.current_block.add_child(target)
            self.current_block.append(InstUncondJump( target.label))
    
    def _build_continue(self, stmt: Continue):
        assert self.current_block is not None, "Current block must be set"
        
        if self.continue_targets:
            target = self.continue_targets[-1]
            self.current_block.add_child(target)
            self.current_block.append(InstUncondJump(target.label))