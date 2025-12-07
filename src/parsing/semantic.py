from .parser import (
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
    """Represents a type, which can be a base type (int, void) or an array type."""
    
    def __init__(self, base_type: str, dimensions: list[int] | None = None):
        self.base_type = base_type
        self.dimensions = dimensions if dimensions is not None else []
    
    def is_array(self) -> bool:
        """Check if this is an array type."""
        return len(self.dimensions) > 0
    
    def get_element_type(self) -> str:
        """Get the base element type (for arrays, returns the base type)."""
        return self.base_type
    
    def __str__(self) -> str:
        """Convert to string representation like '[128][64]int' or 'int'."""
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
            # Simple type like "int" or "void"
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
    """Raised when a semantic error is detected."""

    def __init__(self, message: str, line: int = 0, column: int = 0):
        self.message = message
        self.line = line
        self.column = column
        super().__init__(f"{message} at line {line}, column {column}")


class FunctionInfo:
    """Information about a function."""

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
    """Symbol table for tracking variables and functions."""

    def __init__(self, parent: "SymbolTable | None" = None):
        self.parent = parent
        self.variables: dict[str, Type] = {}  # name -> Type
        self.functions: dict[str, FunctionInfo] = {}  # name -> FunctionInfo

    def __repr__(self):
        return (
            f"SymbolTable(variables={self.variables!r}, functions={self.functions!r})"
        )

    def declare_variable(self, name: str, var_type: Type, line: int, column: int):
        """Declare a variable in the current scope."""
        if name in self.variables:
            raise SemanticError(
                f"Variable '{name}' already declared in this scope", line, column
            )
        self.variables[name] = var_type

    def lookup_variable(self, name: str) -> Type | None:
        """Look up a variable's type, checking parent scopes."""
        if name in self.variables:
            return self.variables[name]
        if self.parent:
            return self.parent.lookup_variable(name)
        return None

    def declare_function(self, func_info: FunctionInfo):
        """Declare a function."""
        if func_info.name in self.functions:
            raise SemanticError(
                f"Function '{func_info.name}' already declared",
                func_info.line,
                func_info.column,
            )
        self.functions[func_info.name] = func_info

    def lookup_function(self, name: str) -> FunctionInfo | None:
        """Look up a function."""
        if name in self.functions:
            return self.functions[name]
        if self.parent:
            return self.parent.lookup_function(name)
        return None


class SemanticAnalyzer:
    """Semantic analyzer for type checking and validation."""

    def __init__(self, program: Program):
        self.program = program
        self.global_scope = SymbolTable()
        self.current_scope: SymbolTable = self.global_scope
        self.current_function: FunctionInfo | None = None
        self.loop_depth: int = (
            0  # Track loop nesting depth for break/continue validation
        )
        self.errors: list[SemanticError] = []

    def analyze(self) -> list[SemanticError]:
        """Perform semantic analysis and return list of errors."""
        self.errors = []

        # Attach global symbol table to Program
        self.program.symbol_table = self.global_scope

        # First pass: collect all function declarations
        for func in self.program.functions:
            self._collect_function(func)

        # Second pass: analyze function bodies
        for func in self.program.functions:
            self._analyze_function(func)

        return self.errors

    def _collect_function(self, func: Function):
        """Collect function declaration into symbol table."""
        param_types = [(arg.name, Type.from_string(arg.type)) for arg in func.args]
        return_type = Type.from_string(func.return_type)
        
        if return_type.is_array():
            self.errors.append(SemanticError("Functions cannot return arrays", func.line, func.column))
        
        func_info = FunctionInfo(
            func.name, return_type, param_types, func.line, func.column
        )

        try:
            self.global_scope.declare_function(func_info)
        except SemanticError as e:
            self.errors.append(e)

    def _analyze_function(self, func: Function):
        """Analyze a function body."""
        # Create new scope for function and attach to function body Block
        func.body.symbol_table = SymbolTable(parent=self.global_scope)
        self.current_scope = func.body.symbol_table

        # Look up function info
        func_info = self.global_scope.lookup_function(func.name)
        if not func_info:
            self.errors.append(
                SemanticError(
                    f"Function '{func.name}' not found in symbol table",
                    func.line,
                    func.column,
                )
            )
            return

        self.current_function = func_info

        # Add parameters to function scope
        for arg in func.args:
            try:
                arg_type = Type.from_string(arg.type)
                self.current_scope.declare_variable(
                    arg.name, arg_type, func.line, func.column
                )
            except SemanticError as e:
                self.errors.append(e)

        # Function body uses function's scope (no new Block scope)
        for statement in func.body.statements:
            self._analyze_statement(statement)

        # Restore scope
        self.current_scope = self.global_scope
        self.current_function = None

    def _analyze_statement(self, stmt: Statement):
        """Analyze a statement."""
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
            case Block():
                self._analyze_block(stmt)
            case _:
                self.errors.append(
                    SemanticError(
                        f"Unknown statement type: {type(stmt).__name__}", 0, 0
                    )
                )

    def _analyze_assignment(self, stmt: Assignment):
        """Analyze an assignment statement."""
        # Convert string type to Type object
        var_type = Type.from_string(stmt.type)
        
        # Check for array initialization
        if isinstance(stmt.value, ArrayInit):
            # Array initialization with {} is only allowed for array types
            if not var_type.is_array():
                self.errors.append(
                    SemanticError(
                        f"Cannot initialize non-array variable '{stmt.name}' of type {var_type} with array syntax",
                        stmt.line,
                        stmt.column,
                    )
                )
                # Still declare the variable for error recovery
                try:
                    self.current_scope.declare_variable(
                        stmt.name, var_type, stmt.line, stmt.column
                    )
                except SemanticError as e:
                    self.errors.append(e)
                return
            
            # Array initialization with {} is allowed for array types
            # Declare variable in current scope
            try:
                self.current_scope.declare_variable(
                    stmt.name, var_type, stmt.line, stmt.column
                )
            except SemanticError as e:
                self.errors.append(e)
            return
        
        # Check that value type matches declared type
        value_type = self._analyze_expression(stmt.value)
        
        # Forbid array-to-array assignment
        if var_type.is_array() and isinstance(value_type, Type) and value_type.is_array():
            self.errors.append(
                SemanticError(
                    f"Cannot assign array to array: cannot assign {value_type} to variable '{stmt.name}' of type {var_type}",
                    stmt.line,
                    stmt.column,
                )
            )
            # Still declare the variable for error recovery
            try:
                self.current_scope.declare_variable(
                    stmt.name, var_type, stmt.line, stmt.column
                )
            except SemanticError as e:
                self.errors.append(e)
            return
        
        # Type checking for non-array assignments
        if value_type != var_type:
            self.errors.append(
                SemanticError(
                    f"Type mismatch: cannot assign {value_type} to variable '{stmt.name}' of type {var_type}",
                    stmt.line,
                    stmt.column,
                )
            )

        # Declare variable in current scope
        try:
            self.current_scope.declare_variable(
                stmt.name, var_type, stmt.line, stmt.column
            )
        except SemanticError as e:
            self.errors.append(e)

    def _analyze_reassignment(self, stmt: Reassignment):
        """Analyze a reassignment statement."""
        # Analyze the lvalue to get the target type
        target_type = self._analyze_lvalue(stmt.lvalue)
        if target_type is None:
            return  # Error already reported
        
        # Check that value type matches target type
        value_type = self._analyze_expression(stmt.value)
        
        # Forbid array-to-array assignment (but allow array element assignment)
        if target_type.is_array() and isinstance(value_type, Type) and value_type.is_array():
            self.errors.append(
                SemanticError(
                    f"Cannot assign array to array: cannot assign {value_type} to array of type {target_type}",
                    stmt.line,
                    stmt.column,
                )
            )
            return
        
        if value_type != target_type:
            self.errors.append(
                SemanticError(
                    f"Type mismatch: cannot assign {value_type} to target of type {target_type}",
                    stmt.line,
                    stmt.column,
                )
            )
    
    def _analyze_lvalue(self, lvalue: LValue) -> Type | None:
        """Analyze an lvalue and return its type."""
        match lvalue:
            case LValueIdentifier():
                var_type = self.current_scope.lookup_variable(lvalue.name)
                if var_type is None:
                    line = getattr(lvalue, 'line', 0)
                    column = getattr(lvalue, 'column', 0)
                    self.errors.append(
                        SemanticError(
                            f"Variable '{lvalue.name}' is not declared", line, column
                        )
                    )
                    return None
                return var_type
            case LValueArrayAccess():
                # Look up the base array variable
                base_type = self.current_scope.lookup_variable(lvalue.base)
                if base_type is None:
                    line = getattr(lvalue, 'line', 0)
                    column = getattr(lvalue, 'column', 0)
                    self.errors.append(
                        SemanticError(
                            f"Variable '{lvalue.base}' is not declared", line, column
                        )
                    )
                    return None
                
                if not isinstance(base_type, Type) or not base_type.is_array():
                    line = getattr(lvalue, 'line', 0)
                    column = getattr(lvalue, 'column', 0)
                    self.errors.append(
                        SemanticError(
                            f"Array access on non-array variable '{lvalue.base}'",
                            line, column
                        )
                    )
                    return None
                
                # Check that number of indices matches number of dimensions
                if len(lvalue.indices) != len(base_type.dimensions):
                    line = getattr(lvalue, 'line', 0)
                    column = getattr(lvalue, 'column', 0)
                    self.errors.append(
                        SemanticError(
                            f"Array access has {len(lvalue.indices)} indices but array has {len(base_type.dimensions)} dimensions",
                            line, column
                        )
                    )
                    return Type(base_type.base_type)  # Return base type for error recovery
                
                # Check that each index is int
                for idx in lvalue.indices:
                    idx_type = self._analyze_expression(idx)
                    if idx_type != Type("int"):
                        line = getattr(lvalue, 'line', 0)
                        column = getattr(lvalue, 'column', 0)
                        self.errors.append(
                            SemanticError(
                                f"Array index must be int, got {idx_type}",
                                line, column
                            )
                        )
                
                # Return the base element type
                return Type(base_type.base_type)
            case _:
                line = getattr(lvalue, 'line', 0)
                column = getattr(lvalue, 'column', 0)
                self.errors.append(
                    SemanticError(
                        f"Unknown lvalue type: {type(lvalue).__name__}", line, column
                    )
                )
                return None

    def _analyze_condition(self, stmt: Condition):
        """Analyze a condition statement."""
        # Condition should be boolean (int in this language)
        cond_type = self._analyze_expression(stmt.condition)
        if cond_type != Type("int"):
            self.errors.append(
                SemanticError(
                    f"Condition expression must be int, got {cond_type}",
                    stmt.line,
                    stmt.column,
                )
            )

        # Analyze then block with new scope and attach to Block node
        old_scope = self.current_scope
        stmt.then_block.symbol_table = SymbolTable(parent=old_scope)
        self.current_scope = stmt.then_block.symbol_table
        for s in stmt.then_block.statements:
            self._analyze_statement(s)
        self.current_scope = old_scope

        # Analyze else block if present with new scope and attach to Block node
        if stmt.else_block:
            stmt.else_block.symbol_table = SymbolTable(parent=old_scope)
            self.current_scope = stmt.else_block.symbol_table
            for s in stmt.else_block.statements:
                self._analyze_statement(s)
            self.current_scope = old_scope

    def _analyze_for_loop(self, stmt: ForLoop):
        """Analyze a C-style for loop statement."""
        # Create new scope for loop and attach to body Block
        old_scope = self.current_scope
        stmt.body.symbol_table = SymbolTable(parent=old_scope)
        self.current_scope = stmt.body.symbol_table

        # Increment loop depth for break/continue validation
        self.loop_depth += 1

        # Analyze init
        self._analyze_assignment(stmt.init)

        # Analyze condition
        cond_type = self._analyze_expression(stmt.condition)
        if cond_type != Type("int"):
            self.errors.append(
                SemanticError(
                    f"Loop condition must be int, got {cond_type}",
                    stmt.line,
                    stmt.column,
                )
            )

        # Analyze update
        self._analyze_reassignment(stmt.update)

        # Analyze body (which is now a Block)
        for s in stmt.body.statements:
            self._analyze_statement(s)

        # Decrement loop depth
        self.loop_depth -= 1

        # Restore scope
        self.current_scope = old_scope

    def _analyze_unconditional_loop(self, stmt: UnconditionalLoop):
        """Analyze an unconditional loop statement."""
        # Create new scope for loop and attach to body Block
        old_scope = self.current_scope

        # Increment loop depth for break/continue validation
        self.loop_depth += 1

        # Analyze body (which is now a Block)
        self._analyze_block(stmt.body)

        # Decrement loop depth
        self.loop_depth -= 1

        # Restore scope
        self.current_scope = old_scope

    def _analyze_function_call_stmt(self, stmt: FunctionCall):
        """Analyze a function call statement."""
        self._check_function_call(stmt.name, stmt.args, stmt.line, stmt.column)

    def _analyze_return(self, stmt: Return):
        """Analyze a return statement."""
        if not self.current_function:
            self.errors.append(
                SemanticError(
                    "Return statement outside of function", stmt.line, stmt.column
                )
            )
            return

        if stmt.value is None:
            # No return value
            if self.current_function.return_type != Type("void"):
                self.errors.append(
                    SemanticError(
                        f"Function '{self.current_function.name}' expects return type {self.current_function.return_type}, but got void",
                        stmt.line,
                        stmt.column,
                    )
                )
        else:
            # Has return value
            if self.current_function.return_type == Type("void"):
                self.errors.append(
                    SemanticError(
                        f"Function '{self.current_function.name}' returns void, but return statement has a value",
                        stmt.line,
                        stmt.column,
                    )
                )
            else:
                value_type = self._analyze_expression(stmt.value)
                if not isinstance(value_type, Type) or value_type != self.current_function.return_type:
                    self.errors.append(
                        SemanticError(
                            f"Return type mismatch: function '{self.current_function.name}' returns {self.current_function.return_type}, but got {value_type}",
                            stmt.line,
                            stmt.column,
                        )
                    )

    def _analyze_break(self, stmt: Break):
        """Analyze a break statement."""
        if self.loop_depth == 0:
            self.errors.append(
                SemanticError("Break statement outside of loop", stmt.line, stmt.column)
            )

    def _analyze_continue(self, stmt: Continue):
        """Analyze a continue statement."""
        if self.loop_depth == 0:
            self.errors.append(
                SemanticError(
                    "Continue statement outside of loop", stmt.line, stmt.column
                )
            )

    def _analyze_block(self, stmt: Block):
        """Analyze a block statement."""
        # Create new scope for block and attach to AST node
        old_scope = self.current_scope
        stmt.symbol_table = SymbolTable(parent=old_scope)
        self.current_scope = stmt.symbol_table

        for s in stmt.statements:
            self._analyze_statement(s)

        # Restore scope
        self.current_scope = old_scope

    def _analyze_expression(self, expr: Expression) -> Type:
        """Analyze an expression and return its type."""
        match expr:
            case IntegerLiteral():
                return Type("int")
            case Identifier():
                var_type = self.current_scope.lookup_variable(expr.name)
                if var_type is None:
                    # Try to get line/column from current function or use defaults
                    line = self.current_function.line if self.current_function else 0
                    column = (
                        self.current_function.column if self.current_function else 0
                    )
                    self.errors.append(
                        SemanticError(
                            f"Variable '{expr.name}' is not declared", line, column
                        )
                    )
                    return Type("int")  # Default to int for error recovery
                return var_type
            case ArrayAccess():
                return self._analyze_array_access(expr)
            case ArrayInit():
                # ArrayInit should only appear in assignments, and type is determined there
                # Return a placeholder - this shouldn't be reached in normal flow
                return Type("int")  # Placeholder
            case BinaryOp():
                return self._analyze_binary_op(expr)
            case UnaryOp():
                return self._analyze_unary_op(expr)
            case CallExpression():
                return self._analyze_call_expression(expr)
            case _:
                self.errors.append(
                    SemanticError(
                        f"Unknown expression type: {type(expr).__name__}", 0, 0
                    )
                )
                return Type("int")  # Default to int for error recovery

    def _analyze_array_access(self, expr: ArrayAccess) -> Type:
        """Analyze an array access expression."""
        # Analyze the base expression
        base_type = self._analyze_expression(expr.base)
        
        if not isinstance(base_type, Type):
            # Error recovery - treat as int
            return Type("int")
        
        if not base_type.is_array():
            self.errors.append(
                SemanticError(
                    f"Array access on non-array type {base_type}",
                    0, 0  # TODO: get line/column from expr
                )
            )
            return Type("int")  # Error recovery
        
        # Check that number of indices matches number of dimensions
        if len(expr.indices) != len(base_type.dimensions):
            self.errors.append(
                SemanticError(
                    f"Array access has {len(expr.indices)} indices but array has {len(base_type.dimensions)} dimensions",
                    0, 0  # TODO: get line/column from expr
                )
            )
            return Type(base_type.base_type)  # Return base type for error recovery
        
        # Check that each index is int
        for idx in expr.indices:
            idx_type = self._analyze_expression(idx)
            if idx_type != Type("int"):
                self.errors.append(
                    SemanticError(
                        f"Array index must be int, got {idx_type}",
                        0, 0  # TODO: get line/column from expr
                    )
                )
        
        # Return the base element type
        return Type(base_type.base_type)
    
    def _analyze_binary_op(self, expr: BinaryOp) -> Type:
        """Analyze a binary operation."""
        left_type = self._analyze_expression(expr.left)
        right_type = self._analyze_expression(expr.right)

        # All operations in this language return int
        # But we should check that operands are int
        if left_type != Type("int"):
            self.errors.append(
                SemanticError(
                    f"Left operand of '{expr.operator}' must be int, got {left_type}",
                    0,
                    0,
                )
            )

        if right_type != Type("int"):
            self.errors.append(
                SemanticError(
                    f"Right operand of '{expr.operator}' must be int, got {right_type}",
                    0,
                    0,
                )
            )

        return Type("int")

    def _analyze_unary_op(self, expr: UnaryOp) -> Type:
        """Analyze a unary operation."""
        operand_type = self._analyze_expression(expr.operand)

        if operand_type != Type("int"):
            self.errors.append(
                SemanticError(
                    f"Operand of '{expr.operator}' must be int, got {operand_type}",
                    0,
                    0,
                )
            )

        return Type("int")

    def _analyze_call_expression(self, expr: CallExpression) -> Type:
        """Analyze a function call expression."""
        # Try to get line/column from current function or use defaults
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
        # Look up function
        func_info = self.current_scope.lookup_function(name)
        if func_info is None:
            self.errors.append(
                SemanticError(f"Function '{name}' is not declared", line, column)
            )
            return None

        # Check argument count
        if len(args) != len(func_info.params):
            self.errors.append(
                SemanticError(
                    f"Function '{name}' expects {len(func_info.params)} arguments, but got {len(args)}",
                    line,
                    column,
                )
            )
            return func_info

        # Check argument types
        for i, (arg_expr, (param_name, param_type)) in enumerate(
            zip(args, func_info.params)
        ):
            arg_type = self._analyze_expression(arg_expr)
            if not isinstance(arg_type, Type) or arg_type != param_type:
                self.errors.append(
                    SemanticError(
                        f"Argument {i + 1} of function '{name}' expects type {param_type}, but got {arg_type}",
                        line,
                        column,
                    )
                )

        # Check for duplicate array variable arguments
        array_vars_seen: dict[str, int] = {}  # variable name -> argument index
        for i, (arg_expr, (param_name, param_type)) in enumerate(
            zip(args, func_info.params)
        ):
            # Only check direct variable references (Identifier), not array element accesses
            if isinstance(arg_expr, Identifier):
                var_name = arg_expr.name
                arg_type = self._analyze_expression(arg_expr)
                # Check if this is an array type
                if isinstance(arg_type, Type) and arg_type.is_array():
                    if var_name in array_vars_seen:
                        self.errors.append(
                            SemanticError(
                                f"Cannot pass the same array variable '{var_name}' as multiple arguments to function '{name}'",
                                line,
                                column,
                            )
                        )
                    else:
                        array_vars_seen[var_name] = i

        return func_info


if __name__ == "__main__":
    # Test the semantic analyzer
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
