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
    LValue,
    LValueIdentifier,
    LValueArrayAccess,
)


class Type:
    def __init__(self, base_type: str, dimensions: list[int] | None = None):
        self.base_type = base_type
        self.dimensions = dimensions if dimensions is not None else []

    def is_array(self) -> bool:
        return len(self.dimensions) > 0

    def get_element_type(self) -> str:
        return self.base_type

    def __str__(self) -> str:
        if not self.is_array():
            return self.base_type
        dims_str = "".join(f"[{d}]" for d in self.dimensions)
        return f"{dims_str}{self.base_type}"

    def __repr__(self) -> str:
        return f"Type({self.__str__()})"

    def __eq__(self, other) -> bool:
        if not isinstance(other, Type):
            return False
        return self.base_type == other.base_type and self.dimensions == other.dimensions

    @staticmethod
    def from_string(type_str: str) -> "Type":
        """Parse a type string like '[128][64]int' or 'int' into a Type object."""
        if not type_str.startswith("["):
            return Type(type_str)

        # Parse array type like "[128][64]int"
        dimensions = []
        pos = 0
        while pos < len(type_str) and type_str[pos] == "[":
            # Find the closing bracket
            end_pos = type_str.find("]", pos)
            if end_pos == -1:
                raise ValueError(f"Invalid array type: {type_str}")
            dim_str = type_str[pos + 1 : end_pos]
            try:
                dimensions.append(int(dim_str))
            except ValueError:
                raise ValueError(f"Invalid array dimension: {dim_str}")
            pos = end_pos + 1

        # The rest is the base type
        base_type = type_str[pos:]
        return Type(base_type, dimensions)


class SemanticError(Exception):
    def __init__(self, message: str, line: int = 0, column: int = 0):
        self.message = message
        self.line = line
        self.column = column
        super().__init__(f"{message} at line {line}, column {column}")


class FunctionInfo:
    def __init__(
        self,
        name: str,
        return_type: Type,
        params: list[tuple[str, Type]],
        line: int,
        column: int,
    ):
        self.name = name
        self.return_type = return_type
        self.params = params  # List of (name, Type) tuples
        self.line = line
        self.column = column

    def __repr__(self):
        param_str = ", ".join(f"{name} {type}" for name, type in self.params)
        return f"FunctionInfo({self.name}({param_str}) -> {self.return_type})"


class SymbolTable:
    def __init__(self, parent: "SymbolTable | None" = None):
        self.parent = parent
        self.variables: dict[str, Type] = {}
        self.functions: dict[str, FunctionInfo] = {}

    def __str__(self):
        variables_str = ", ".join(
            f"{name}: {type_}" for name, type_ in self.variables.items()
        )
        functions_str = ", ".join(
            f"{name}: {info}" for name, info in self.functions.items()
        )
        return f"SymbolTable:\n\tVariables: {{{variables_str}}}\n\tFunctions: {{{functions_str}}}"

    def __repr__(self):
        return (
            f"SymbolTable(variables={self.variables!r}, functions={self.functions!r})"
        )

    def declare_variable(self, name: str, var_type: Type, line: int, column: int):
        if name in self.variables:
            raise SemanticError(
                f"Variable '{name}' already declared in this scope", line, column
            )
        self.variables[name] = var_type

    def lookup_variable(self, name: str) -> Type | None:
        if name in self.variables:
            return self.variables[name]
        if self.parent:
            return self.parent.lookup_variable(name)
        return None

    def declare_function(self, func_info: FunctionInfo):
        if func_info.name in self.functions:
            raise SemanticError(
                f"Function '{func_info.name}' already declared",
                func_info.line,
                func_info.column,
            )
        self.functions[func_info.name] = func_info

    def lookup_function(self, name: str) -> FunctionInfo | None:
        if name in self.functions:
            return self.functions[name]
        if self.parent:
            return self.parent.lookup_function(name)
        return None


class SemanticAnalyzer:
    def __init__(self, program: Program):
        self.program = program
        self.global_scope = SymbolTable()
        self.current_scope: SymbolTable = self.global_scope
        self.current_function: FunctionInfo | None = None

        # Track loop nesting depth for break/continue validation
        self.loop_depth: int = 0

        self.errors: list[SemanticError] = []

    def analyze(self) -> list[SemanticError]:
        self.errors = []
        self.program.symbol_table = self.global_scope

        for func in self.program.functions:
            self._collect_function(func)

        for func in self.program.functions:
            self._analyze_function(func)

        return self.errors

    def _collect_function(self, func: Function):
        param_types = [(arg.name, Type.from_string(arg.type)) for arg in func.args]
        return_type = Type.from_string(func.return_type)

        if return_type.is_array():
            msg = "Functions cannot return arrays"
            self.errors.append(SemanticError(msg, func.line, func.column))

        func_info = FunctionInfo(
            func.name, return_type, param_types, func.line, func.column
        )

        try:
            self.global_scope.declare_function(func_info)
        except SemanticError as e:
            self.errors.append(e)

    def _analyze_function(self, func: Function):
        func.body.symbol_table = SymbolTable(parent=self.global_scope)
        self.current_scope = func.body.symbol_table

        func_info = self.global_scope.lookup_function(func.name)
        if not func_info:
            msg = f"Function '{func.name}' not found in symbol table"
            self.errors.append(SemanticError(msg, func.line, func.column))
            return

        self.current_function = func_info

        for arg in func.args:
            try:
                arg_type = Type.from_string(arg.type)
                self.current_scope.declare_variable(
                    arg.name, arg_type, func.line, func.column
                )
            except SemanticError as e:
                self.errors.append(e)

        for statement in func.body.statements:
            self._analyze_statement(statement)

        self.current_scope = self.global_scope
        self.current_function = None

    def _analyze_statement(self, stmt: Statement):
        match stmt:
            case Assignment():
                self._analyze_assignment(stmt)
            case Reassignment():
                self._analyze_reassignment(stmt)
            case Condition():
                self._analyze_condition(stmt)
            case ForLoop():
                self._analyze_for_loop(stmt)
            case UnconditionalLoop():
                self._analyze_unconditional_loop(stmt)
            case FunctionCall():
                self._analyze_function_call_stmt(stmt)
            case Return():
                self._analyze_return(stmt)
            case Break():
                self._analyze_break(stmt)
            case Continue():
                self._analyze_continue(stmt)
            case _:
                msg = f"Unknown statement type: {type(stmt).__name__}"
                self.errors.append(SemanticError(msg, stmt.line, stmt.column))

    def _analyze_assignment(self, stmt: Assignment):
        if self.current_scope.lookup_variable(stmt.name) is not None:
            msg = f"Variable '{stmt.name}' already declared in this scope"
            self.errors.append(SemanticError(msg, stmt.line, stmt.column))
            return

        var_type = Type.from_string(stmt.type)
        if isinstance(stmt.value, ArrayInit):
            if not var_type.is_array():
                msg = f"Cannot initialize non-array variable '{stmt.name}' of type {var_type} with array syntax"
                self.errors.append(SemanticError(msg, stmt.line, stmt.column))

            self.current_scope.declare_variable(
                stmt.name, var_type, stmt.line, stmt.column
            )
            return

        value_type = self._analyze_expression(stmt.value)
        if var_type.is_array() and value_type.is_array():
            msg = f"Cannot assign array to array: cannot assign {value_type} to variable '{stmt.name}' of type {var_type}"
            self.errors.append(SemanticError(msg, stmt.line, stmt.column))
            self.current_scope.declare_variable(
                stmt.name, var_type, stmt.line, stmt.column
            )
            return

        if value_type != var_type:
            msg = f"Type mismatch: cannot assign {value_type} to variable '{stmt.name}' of type {var_type}"
            self.errors.append(SemanticError(msg, stmt.line, stmt.column))

        self.current_scope.declare_variable(stmt.name, var_type, stmt.line, stmt.column)

    def _analyze_reassignment(self, stmt: Reassignment):
        target_type = self._analyze_lvalue(stmt.lvalue)
        if target_type is None:
            return  # Error already reported

        value_type = self._analyze_expression(stmt.value)
        # Forbid array-to-array assignment (but allow array element assignment)
        if target_type.is_array() and value_type.is_array():
            msg = f"Cannot assign array to array: cannot assign {value_type} to array of type {target_type}"
            self.errors.append(SemanticError(msg, stmt.line, stmt.column))
            return

        if value_type != target_type:
            msg = f"Type mismatch: cannot assign {value_type} to target of type {target_type}"
            self.errors.append(SemanticError(msg, stmt.line, stmt.column))

    def _analyze_lvalue(self, lvalue: LValue) -> Type | None:
        match lvalue:
            case LValueIdentifier():
                var_type = self.current_scope.lookup_variable(lvalue.name)
                if var_type is None:
                    msg = f"Variable '{lvalue.name}' is not declared"
                    self.errors.append(SemanticError(msg, lvalue.line, lvalue.column))
                    return None
                return var_type
            case LValueArrayAccess():
                base_type = self.current_scope.lookup_variable(lvalue.base)
                if base_type is None:
                    msg = f"Variable '{lvalue.base}' is not declared"
                    self.errors.append(SemanticError(msg, lvalue.line, lvalue.column))
                    return None

                if not base_type.is_array():
                    msg = f"Array access on non-array variable '{lvalue.base}'"
                    self.errors.append(SemanticError(msg, lvalue.line, lvalue.column))
                    return None

                if len(lvalue.indices) != len(base_type.dimensions):
                    msg = f"Array access has {len(lvalue.indices)} indices but array has {len(base_type.dimensions)} dimensions"
                    self.errors.append(SemanticError(msg, lvalue.line, lvalue.column))
                    return Type(base_type.base_type)  # error recovery

                # Check that each index is int
                for idx in lvalue.indices:
                    idx_type = self._analyze_expression(idx)
                    if idx_type == Type("int"):
                        continue
                    msg = f"Array index must be int, got {idx_type}"
                    self.errors.append(SemanticError(msg, lvalue.line, lvalue.column))

                return Type(base_type.base_type)
            case _:
                msg = f"Unknown lvalue type: {type(lvalue).__name__}"
                self.errors.append(SemanticError(msg, lvalue.line, lvalue.column))
                return None

    def _analyze_condition(self, stmt: Condition):
        cond_type = self._analyze_expression(stmt.condition)
        if cond_type != Type("int"):
            msg = f"Condition expression must be int, got {cond_type}"
            self.errors.append(SemanticError(msg, stmt.line, stmt.column))

        old_scope = self.current_scope
        stmt.then_block.symbol_table = SymbolTable(parent=old_scope)
        self.current_scope = stmt.then_block.symbol_table
        for s in stmt.then_block.statements:
            self._analyze_statement(s)
        self.current_scope = old_scope

        if stmt.else_block:
            stmt.else_block.symbol_table = SymbolTable(parent=old_scope)
            self.current_scope = stmt.else_block.symbol_table
            for s in stmt.else_block.statements:
                self._analyze_statement(s)
            self.current_scope = old_scope

    def _analyze_for_loop(self, stmt: ForLoop):
        # Create new scope for loop and attach to body Block
        old_scope = self.current_scope
        stmt.body.symbol_table = SymbolTable(parent=old_scope)
        self.current_scope = stmt.body.symbol_table

        self.loop_depth += 1
        self._analyze_assignment(stmt.init)

        cond_type = self._analyze_expression(stmt.condition)
        if cond_type != Type("int"):
            msg = f"Loop condition must be int, got {cond_type}"
            self.errors.append(SemanticError(msg, stmt.line, stmt.column))

        self._analyze_reassignment(stmt.update)

        for s in stmt.body.statements:
            self._analyze_statement(s)

        self.loop_depth -= 1
        self.current_scope = old_scope

    def _analyze_unconditional_loop(self, stmt: UnconditionalLoop):
        old_scope = self.current_scope

        self.loop_depth += 1
        self._analyze_block(stmt.body)
        self.loop_depth -= 1

        self.current_scope = old_scope

    def _analyze_function_call_stmt(self, stmt: FunctionCall):
        self._check_function_call(stmt.name, stmt.args, stmt.line, stmt.column)

    def _analyze_return(self, stmt: Return):
        if not self.current_function:
            msg = "Return statement outside of function"
            self.errors.append(SemanticError(msg, stmt.line, stmt.column))
            return

        if stmt.value is None:
            if self.current_function.return_type != Type("void"):
                msg = f"Function '{self.current_function.name}' expects return type {self.current_function.return_type}, but got void"
                self.errors.append(SemanticError(msg, stmt.line, stmt.column))
            return

        if self.current_function.return_type == Type("void"):
            msg = f"Function '{self.current_function.name}' returns void, but return statement has a value"
            self.errors.append(SemanticError(msg, stmt.line, stmt.column))
            return

        value_type = self._analyze_expression(stmt.value)
        if value_type != self.current_function.return_type:
            msg = f"Return type mismatch: function '{self.current_function.name}' returns {self.current_function.return_type}, but got {value_type}"
            self.errors.append(SemanticError(msg, stmt.line, stmt.column))

    def _analyze_break(self, stmt: Break):
        if self.loop_depth == 0:
            msg = "Break statement outside of loop"
            self.errors.append(SemanticError(msg, stmt.line, stmt.column))

    def _analyze_continue(self, stmt: Continue):
        if self.loop_depth == 0:
            msg = "Continue statement outside of loop"
            self.errors.append(SemanticError(msg, stmt.line, stmt.column))

    def _analyze_block(self, stmt: Block):
        old_scope = self.current_scope
        stmt.symbol_table = SymbolTable(parent=old_scope)
        self.current_scope = stmt.symbol_table

        for s in stmt.statements:
            self._analyze_statement(s)

        self.current_scope = old_scope

    def _analyze_expression(self, expr: Expression) -> Type:
        match expr:
            case IntegerLiteral():
                return Type("int")
            case Identifier():
                var_type = self.current_scope.lookup_variable(expr.name)
                if var_type is not None:
                    return var_type
                line = self.current_function.line if self.current_function else 0
                column = self.current_function.column if self.current_function else 0
                msg = f"Variable '{expr.name}' is not declared"
                self.errors.append(SemanticError(msg, line, column))
                return Type("int")  # Default to int for error recovery
            case ArrayAccess():
                return self._analyze_array_access(expr)
            case ArrayInit():
                # ArrayInit should only appear in assignments, and type is determined there
                # Return a placeholder - this shouldn't be reached in normal flow
                return Type("int")
            case BinaryOp():
                return self._analyze_binary_op(expr)
            case UnaryOp():
                return self._analyze_unary_op(expr)
            case CallExpression():
                return self._analyze_call_expression(expr)
            case _:
                msg = f"Unknown expression type: {type(expr).__name__}"
                self.errors.append(SemanticError(msg, 0, 0))
                return Type("int")  # Default to int for error recovery

    def _analyze_array_access(self, expr: ArrayAccess) -> Type:
        base_type = self._analyze_expression(expr.base)
        if not base_type.is_array():
            msg = f"Array access on non-array type {base_type}"
            self.errors.append(SemanticError(msg, expr.line, expr.column))
            return Type("int")  # Error recovery

        if len(expr.indices) != len(base_type.dimensions):
            msg = f"Array access has {len(expr.indices)} indices but array has {len(base_type.dimensions)} dimensions"
            self.errors.append(SemanticError(msg, expr.line, expr.column))
            return Type(base_type.base_type)  # Return base type for error recovery

        for idx in expr.indices:
            idx_type = self._analyze_expression(idx)
            if idx_type != Type("int"):
                msg = f"Array index must be int, got {idx_type}"
                self.errors.append(SemanticError(msg, expr.line, expr.column))

        # Return the base element type
        return Type(base_type.base_type)

    def _analyze_binary_op(self, expr: BinaryOp) -> Type:
        left_type = self._analyze_expression(expr.left)
        right_type = self._analyze_expression(expr.right)

        if left_type != Type("int"):
            msg = f"Left operand of '{expr.operator}' must be int, got {left_type}"
            self.errors.append(SemanticError(msg, expr.line, expr.column))

        if right_type != Type("int"):
            msg = f"Right operand of '{expr.operator}' must be int, got {right_type}"
            self.errors.append(SemanticError(msg, expr.line, expr.column))

        return Type("int")

    def _analyze_unary_op(self, expr: UnaryOp) -> Type:
        operand_type = self._analyze_expression(expr.operand)

        if operand_type != Type("int"):
            msg = f"Operand of '{expr.operator}' must be int, got {operand_type}"
            self.errors.append(SemanticError(msg, expr.line, expr.column))

        return Type("int")

    def _analyze_call_expression(self, expr: CallExpression) -> Type:
        line = self.current_function.line if self.current_function else 0
        column = self.current_function.column if self.current_function else 0
        func_info = self._check_function_call(expr.name, expr.args, line, column)
        if func_info:
            return func_info.return_type
        return Type("int")  # Default for error recovery

    def _check_function_call(
        self, name: str, args: list[Expression], line: int, column: int
    ) -> FunctionInfo | None:
        """Check that a function call is valid."""
        func_info = self.current_scope.lookup_function(name)
        if func_info is None:
            msg = f"Function '{name}' is not declared"
            self.errors.append(SemanticError(msg, line, column))
            return None

        if len(args) != len(func_info.params):
            msg = f"Function '{name}' expects {len(func_info.params)} arguments, but got {len(args)}"
            self.errors.append(SemanticError(msg, line, column))
            return func_info

        for i, (arg_expr, (param_name, param_type)) in enumerate(
            zip(args, func_info.params)
        ):
            arg_type = self._analyze_expression(arg_expr)
            if arg_type != param_type:
                msg = f"Argument {i + 1} of function '{name}' expects type {param_type}, but got {arg_type}"
                self.errors.append(SemanticError(msg, line, column))

        array_vars_seen: dict[str, int] = {}  # variable name -> argument index
        for i, (arg_expr, (param_name, param_type)) in enumerate(
            zip(args, func_info.params)
        ):
            if isinstance(arg_expr, Identifier):
                var_name = arg_expr.name
                arg_type = self._analyze_expression(arg_expr)
                if arg_type.is_array():
                    if var_name in array_vars_seen:
                        msg = f"Cannot pass the same array variable '{var_name}' as multiple arguments to function '{name}'"
                        self.errors.append(SemanticError(msg, line, column))
                    else:
                        array_vars_seen[var_name] = i

        return func_info


if __name__ == "__main__":
    from .lexer import Lexer
    from .parser import Parser

    test_code = """func foo(x int, y int) -> int {
    return x + y;
}

func main() -> void {
    a int = 1;
    b int = 2;
    c int = foo(a, b);
    d int = foo(1, 2, 3);  // Error: wrong argument count
    e int = bar(1, 2);  // Error: function doesn't exist
    return;
}"""

    lexer = Lexer(test_code)
    parser = Parser(lexer)

    try:
        ast = parser.parse()
        analyzer = SemanticAnalyzer(ast)
        errors = analyzer.analyze()

        if errors:
            print("Semantic errors found:")
            for error in errors:
                print(f"  {error}")
        else:
            print("Semantic analysis passed!")
    except Exception as e:
        print(f"Error: {e}")
