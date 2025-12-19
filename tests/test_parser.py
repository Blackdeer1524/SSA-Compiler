import unittest
from src.parsing.lexer import Lexer
from src.parsing.parser import (
    Parser,
    ParseError,
    Program,
    Function,
    Argument,
    Assignment,
    Reassignment,
    Condition,
    ForLoop,
    UnconditionalLoop,
    FunctionCall,
    Return,
    Block,
    BinaryOp,
    UnaryOp,
    Identifier,
    IntegerLiteral,
    CallExpression,
)


class TestParser(unittest.TestCase):
    """Unit tests for the Parser class."""

    def parse_source(self, source: str) -> Program:
        """Helper method to parse source code."""
        lexer = Lexer(source)
        parser = Parser(lexer)
        return parser.parse()

    def test_empty_program(self):
        """Test parsing empty program."""
        # Empty program is not valid (no functions)
        self.assertRaises(ParseError, lambda: self.parse_source(""))

    def test_simple_function_void(self):
        """Test parsing a simple void function."""
        source = "func main() -> void { }"
        ast = self.parse_source(source)

        self.assertEqual(len(ast.functions), 1)
        func = ast.functions[0]
        self.assertEqual(func.name, "main")
        self.assertEqual(func.return_type, "void")
        self.assertEqual(len(func.args), 0)
        self.assertEqual(len(func.body.statements), 0)

    def test_simple_function_int(self):
        """Test parsing a simple int function."""
        source = "func foo() -> int { return 1; }"
        ast = self.parse_source(source)

        self.assertEqual(len(ast.functions), 1)
        func = ast.functions[0]
        self.assertEqual(func.name, "foo")
        self.assertEqual(func.return_type, "int")
        self.assertEqual(len(func.args), 0)
        self.assertEqual(len(func.body.statements), 1)
        self.assertIsInstance(func.body.statements[0], Return)

    def test_function_with_arguments(self):
        """Test parsing function with arguments."""
        source = "func add(x int, y int) -> int { return x; }"
        ast = self.parse_source(source)

        func = ast.functions[0]
        self.assertEqual(len(func.args), 2)
        self.assertEqual(func.args[0].name, "x")
        self.assertEqual(func.args[0].type, "int")
        self.assertEqual(func.args[1].name, "y")
        self.assertEqual(func.args[1].type, "int")

    def test_function_multiple_arguments(self):
        """Test parsing function with multiple arguments."""
        source = "func foo(a int, b int, c int) -> void { }"
        ast = self.parse_source(source)

        func = ast.functions[0]
        self.assertEqual(len(func.args), 3)
        self.assertEqual(func.args[0].name, "a")
        self.assertEqual(func.args[1].name, "b")
        self.assertEqual(func.args[2].name, "c")

    def test_multiple_functions(self):
        """Test parsing multiple functions."""
        source = """func foo() -> void { }
func bar() -> int { return 1; }"""
        ast = self.parse_source(source)

        self.assertEqual(len(ast.functions), 2)
        self.assertEqual(ast.functions[0].name, "foo")
        self.assertEqual(ast.functions[1].name, "bar")

    def test_assignment_statement(self):
        """Test parsing assignment statement."""
        source = "func main() -> void { let a int = 1; }"
        ast = self.parse_source(source)

        stmt = ast.functions[0].body.statements[0]
        self.assertIsInstance(stmt, Assignment)
        self.assertEqual(stmt.name, "a")
        self.assertEqual(stmt.type, "int")
        self.assertIsInstance(stmt.value, IntegerLiteral)
        self.assertEqual(stmt.value.value, 1)

    def test_reassignment_statement(self):
        """Test parsing reassignment statement."""
        source = "func main() -> void { let a int = 1; a = 2; }"
        ast = self.parse_source(source)

        reassign = ast.functions[0].body.statements[1]
        self.assertIsInstance(reassign, Reassignment)
        from src.parsing.parser import LValueIdentifier

        self.assertIsInstance(reassign.lvalue, LValueIdentifier)
        self.assertEqual(reassign.lvalue.name, "a")
        self.assertIsInstance(reassign.value, IntegerLiteral)
        self.assertEqual(reassign.value.value, 2)

    def test_return_statement_with_value(self):
        """Test parsing return statement with value."""
        source = "func foo() -> int { return 42; }"
        ast = self.parse_source(source)

        ret = ast.functions[0].body.statements[0]
        self.assertIsInstance(ret, Return)
        self.assertIsNotNone(ret.value)
        self.assertIsInstance(ret.value, IntegerLiteral)
        self.assertEqual(ret.value.value, 42)

    def test_return_statement_without_value(self):
        """Test parsing return statement without value."""
        source = "func foo() -> void { return; }"
        ast = self.parse_source(source)

        ret = ast.functions[0].body.statements[0]
        self.assertIsInstance(ret, Return)
        self.assertIsNone(ret.value)

    def test_function_call_statement(self):
        """Test parsing function call statement."""
        source = "func main() -> void { foo(1, 2); }"
        ast = self.parse_source(source)

        call = ast.functions[0].body.statements[0]
        self.assertIsInstance(call, FunctionCall)
        self.assertEqual(call.name, "foo")
        self.assertEqual(len(call.args), 2)
        self.assertIsInstance(call.args[0], IntegerLiteral)
        self.assertIsInstance(call.args[1], IntegerLiteral)

    def test_function_call_no_arguments(self):
        """Test parsing function call with no arguments."""
        source = "func main() -> void { foo(); }"
        ast = self.parse_source(source)

        call = ast.functions[0].body.statements[0]
        self.assertIsInstance(call, FunctionCall)
        self.assertEqual(call.name, "foo")
        self.assertEqual(len(call.args), 0)

    def test_if_statement(self):
        """Test parsing if statement."""
        source = "func main() -> void { if (a < 10) { } }"
        ast = self.parse_source(source)

        stmt = ast.functions[0].body.statements[0]
        self.assertIsInstance(stmt, Condition)
        self.assertIsInstance(stmt.condition, BinaryOp)
        self.assertEqual(len(stmt.then_block.statements), 0)
        self.assertIsNone(stmt.else_block)

    def test_if_else_statement(self):
        """Test parsing if-else statement."""
        source = "func main() -> void { if (a < 10) { } else { } }"
        ast = self.parse_source(source)

        stmt = ast.functions[0].body.statements[0]
        self.assertIsInstance(stmt, Condition)
        self.assertIsNotNone(stmt.else_block)
        self.assertEqual(len(stmt.else_block.statements), 0)

    def test_unconditional_loop(self):
        """Test parsing unconditional loop."""
        source = "func main() -> void { for { } }"
        ast = self.parse_source(source)

        stmt = ast.functions[0].body.statements[0]
        self.assertIsInstance(stmt, UnconditionalLoop)
        self.assertEqual(len(stmt.body.statements), 0)

    def test_for_loop(self):
        """Test parsing C-style for loop."""
        source = "func main() -> void { for (let i int = 0; i < 10; i = i + 1) { } }"
        ast = self.parse_source(source)

        stmt = ast.functions[0].body.statements[0]
        self.assertIsInstance(stmt, ForLoop)
        self.assertIsInstance(stmt.init, Assignment)
        self.assertEqual(stmt.init.name, "i")
        self.assertIsInstance(stmt.condition, BinaryOp)
        self.assertIsInstance(stmt.update, Reassignment)
        self.assertEqual(stmt.update.lvalue.name, "i")

    # Expression tests

    def test_integer_literal(self):
        """Test parsing integer literal."""
        source = "func main() -> void { let a int = 42; }"
        ast = self.parse_source(source)

        expr = ast.functions[0].body.statements[0].value
        self.assertIsInstance(expr, IntegerLiteral)
        self.assertEqual(expr.value, 42)

    def test_identifier_expression(self):
        """Test parsing identifier expression."""
        source = "func main() -> void { let a int = x; }"
        ast = self.parse_source(source)

        expr = ast.functions[0].body.statements[0].value
        self.assertIsInstance(expr, Identifier)
        self.assertEqual(expr.name, "x")

    def test_binary_addition(self):
        """Test parsing binary addition."""
        source = "func main() -> void { let a int = 1 + 2; }"
        ast = self.parse_source(source)

        expr = ast.functions[0].body.statements[0].value
        self.assertIsInstance(expr, BinaryOp)
        self.assertEqual(expr.operator, "+")
        self.assertIsInstance(expr.left, IntegerLiteral)
        self.assertIsInstance(expr.right, IntegerLiteral)

    def test_binary_subtraction(self):
        """Test parsing binary subtraction."""
        source = "func main() -> void { let a int = 5 - 3; }"
        ast = self.parse_source(source)

        expr = ast.functions[0].body.statements[0].value
        self.assertIsInstance(expr, BinaryOp)
        self.assertEqual(expr.operator, "-")

    def test_binary_multiplication(self):
        """Test parsing binary multiplication."""
        source = "func main() -> void { let a int = 2 * 3; }"
        ast = self.parse_source(source)

        expr = ast.functions[0].body.statements[0].value
        self.assertIsInstance(expr, BinaryOp)
        self.assertEqual(expr.operator, "*")

    def test_binary_division(self):
        """Test parsing binary division."""
        source = "func main() -> void { let a int = 10 / 2; }"
        ast = self.parse_source(source)

        expr = ast.functions[0].body.statements[0].value
        self.assertIsInstance(expr, BinaryOp)
        self.assertEqual(expr.operator, "/")

    def test_binary_modulo(self):
        """Test parsing binary modulo."""
        source = "func main() -> void { let a int = 10 % 3; }"
        ast = self.parse_source(source)

        expr = ast.functions[0].body.statements[0].value
        self.assertIsInstance(expr, BinaryOp)
        self.assertEqual(expr.operator, "%")

    def test_binary_comparison_less(self):
        """Test parsing less than comparison."""
        source = "func main() -> void { let a int = 1 < 2; }"
        ast = self.parse_source(source)

        expr = ast.functions[0].body.statements[0].value
        self.assertIsInstance(expr, BinaryOp)
        self.assertEqual(expr.operator, "<")

    def test_binary_comparison_less_equal(self):
        """Test parsing less than or equal comparison."""
        source = "func main() -> void { let a int = 1 <= 2; }"
        ast = self.parse_source(source)

        expr = ast.functions[0].body.statements[0].value
        self.assertIsInstance(expr, BinaryOp)
        self.assertEqual(expr.operator, "<=")

    def test_binary_comparison_greater(self):
        """Test parsing greater than comparison."""
        source = "func main() -> void { let a int = 2 > 1; }"
        ast = self.parse_source(source)

        expr = ast.functions[0].body.statements[0].value
        self.assertIsInstance(expr, BinaryOp)
        self.assertEqual(expr.operator, ">")

    def test_binary_comparison_greater_equal(self):
        """Test parsing greater than or equal comparison."""
        source = "func main() -> void { let a int = 2 >= 1; }"
        ast = self.parse_source(source)

        expr = ast.functions[0].body.statements[0].value
        self.assertIsInstance(expr, BinaryOp)
        self.assertEqual(expr.operator, ">=")

    def test_binary_equality(self):
        """Test parsing equality comparison."""
        source = "func main() -> void { let a int = 1 == 1; }"
        ast = self.parse_source(source)

        expr = ast.functions[0].body.statements[0].value
        self.assertIsInstance(expr, BinaryOp)
        self.assertEqual(expr.operator, "==")

    def test_binary_not_equal(self):
        """Test parsing not equal comparison."""
        source = "func main() -> void { let a int = 1 != 2; }"
        ast = self.parse_source(source)

        expr = ast.functions[0].body.statements[0].value
        self.assertIsInstance(expr, BinaryOp)
        self.assertEqual(expr.operator, "!=")

    def test_binary_and(self):
        """Test parsing logical AND."""
        source = "func main() -> void { let a int = 1 && 2; }"
        ast = self.parse_source(source)

        expr = ast.functions[0].body.statements[0].value
        self.assertIsInstance(expr, BinaryOp)
        self.assertEqual(expr.operator, "&&")

    def test_binary_or(self):
        """Test parsing logical OR."""
        source = "func main() -> void { let a int = 1 || 2; }"
        ast = self.parse_source(source)

        expr = ast.functions[0].body.statements[0].value
        self.assertIsInstance(expr, BinaryOp)
        self.assertEqual(expr.operator, "||")

    def test_unary_minus(self):
        """Test parsing unary minus."""
        source = "func main() -> void { let a int = -1; }"
        ast = self.parse_source(source)

        expr = ast.functions[0].body.statements[0].value
        self.assertIsInstance(expr, UnaryOp)
        self.assertEqual(expr.operator, "-")
        self.assertIsInstance(expr.operand, IntegerLiteral)

    def test_unary_not(self):
        """Test parsing unary NOT."""
        source = "func main() -> void { let a int = !1; }"
        ast = self.parse_source(source)

        expr = ast.functions[0].body.statements[0].value
        self.assertIsInstance(expr, UnaryOp)
        self.assertEqual(expr.operator, "!")

    def test_nested_unary(self):
        """Test parsing nested unary operators."""
        source = "func main() -> void { let a int = --1; }"
        ast = self.parse_source(source)

        expr = ast.functions[0].body.statements[0].value
        self.assertIsInstance(expr, UnaryOp)
        self.assertEqual(expr.operator, "-")
        self.assertIsInstance(expr.operand, UnaryOp)
        self.assertEqual(expr.operand.operator, "-")

    def test_parenthesized_expression(self):
        """Test parsing parenthesized expression."""
        source = "func main() -> void { let a int = (1 + 2); }"
        ast = self.parse_source(source)

        expr = ast.functions[0].body.statements[0].value
        self.assertIsInstance(expr, BinaryOp)
        self.assertEqual(expr.operator, "+")

    def test_operator_precedence_multiplication_before_addition(self):
        """Test operator precedence: multiplication before addition."""
        source = "func main() -> void { let a int = 1 + 2 * 3; }"
        ast = self.parse_source(source)

        expr = ast.functions[0].body.statements[0].value
        # Should be: 1 + (2 * 3)
        self.assertIsInstance(expr, BinaryOp)
        self.assertEqual(expr.operator, "+")
        self.assertIsInstance(expr.left, IntegerLiteral)
        self.assertIsInstance(expr.right, BinaryOp)
        self.assertEqual(expr.right.operator, "*")

    def test_operator_precedence_addition_before_comparison(self):
        """Test operator precedence: addition before comparison."""
        source = "func main() -> void { let a int = 1 + 2 < 10; }"
        ast = self.parse_source(source)

        expr = ast.functions[0].body.statements[0].value
        # Should be: (1 + 2) < 10
        self.assertIsInstance(expr, BinaryOp)
        self.assertEqual(expr.operator, "<")
        self.assertIsInstance(expr.left, BinaryOp)
        self.assertEqual(expr.left.operator, "+")

    def test_operator_precedence_comparison_before_logical(self):
        """Test operator precedence: comparison before logical."""
        source = "func main() -> void { let a int = 1 < 2 && 3 > 4; }"
        ast = self.parse_source(source)

        expr = ast.functions[0].body.statements[0].value
        # Should be: (1 < 2) && (3 > 4)
        self.assertIsInstance(expr, BinaryOp)
        self.assertEqual(expr.operator, "&&")
        self.assertIsInstance(expr.left, BinaryOp)
        self.assertEqual(expr.left.operator, "<")
        self.assertIsInstance(expr.right, BinaryOp)
        self.assertEqual(expr.right.operator, ">")

    def test_operator_precedence_logical_and_before_or(self):
        """Test operator precedence: AND before OR."""
        source = "func main() -> void { let a int = 1 || 2 && 3; }"
        ast = self.parse_source(source)

        expr = ast.functions[0].body.statements[0].value
        # Should be: 1 || (2 && 3)
        self.assertIsInstance(expr, BinaryOp)
        self.assertEqual(expr.operator, "||")
        self.assertIsInstance(expr.right, BinaryOp)
        self.assertEqual(expr.right.operator, "&&")

    def test_function_call_in_expression(self):
        """Test parsing function call in expression."""
        source = "func main() -> void { let a int = foo(1, 2); }"
        ast = self.parse_source(source)

        expr = ast.functions[0].body.statements[0].value
        self.assertIsInstance(expr, CallExpression)
        self.assertEqual(expr.name, "foo")
        self.assertEqual(len(expr.args), 2)

    def test_complex_expression(self):
        """Test parsing complex expression."""
        source = "func main() -> void { let a int = (1 + 2) * (3 - 4); }"
        ast = self.parse_source(source)

        expr = ast.functions[0].body.statements[0].value
        self.assertIsInstance(expr, BinaryOp)
        self.assertEqual(expr.operator, "*")
        self.assertIsInstance(expr.left, BinaryOp)
        self.assertEqual(expr.left.operator, "+")
        self.assertIsInstance(expr.right, BinaryOp)
        self.assertEqual(expr.right.operator, "-")

    def test_nested_statements(self):
        """Test parsing nested statements."""
        source = """func main() -> void {
    if (a < 10) {
        if (b > 5) {
            let c int = 1;
        }
    }
}"""
        ast = self.parse_source(source)

        outer_if = ast.functions[0].body.statements[0]
        self.assertIsInstance(outer_if, Condition)
        inner_if = outer_if.then_block.statements[0]
        self.assertIsInstance(inner_if, Condition)
        self.assertIsInstance(inner_if.then_block.statements[0], Assignment)

    def test_for_loop_with_statements(self):
        """Test parsing for loop with body statements."""
        source = """func main() -> void {
    for (let i int = 0; i < 10; i = i + 1) {
        let a int = i;
    }
}"""
        ast = self.parse_source(source)

        loop = ast.functions[0].body.statements[0]
        self.assertIsInstance(loop, ForLoop)
        self.assertEqual(len(loop.body.statements), 1)
        self.assertIsInstance(loop.body.statements[0], Assignment)

    def test_complex_program(self):
        """Test parsing a complex program."""
        source = """func add(x int, y int) -> int {
    return x + y;
}

func main() -> void {
    let a int = 1;
    let b int = 2;
    let c int = add(a, b);
    if (c > 0) {
        let d int = c * 2;
    } else {
        let d int = 0;
    }
    for (let i int = 0; i < 10; i = i + 1) {
        a = a + i;
    }
    return;
}"""
        ast = self.parse_source(source)

        self.assertEqual(len(ast.functions), 2)
        self.assertEqual(ast.functions[0].name, "add")
        self.assertEqual(ast.functions[1].name, "main")
        self.assertEqual(len(ast.functions[1].body.statements), 6)

    # Error cases

    def test_missing_function_name(self):
        """Test error when function name is missing."""
        source = "func () -> void { }"
        lexer = Lexer(source)
        parser = Parser(lexer)
        with self.assertRaises(ParseError):
            parser.parse()

    def test_missing_left_paren(self):
        """Test error when left parenthesis is missing."""
        source = "func main ) -> void { }"
        lexer = Lexer(source)
        parser = Parser(lexer)
        with self.assertRaises(ParseError):
            parser.parse()

    def test_missing_right_paren(self):
        """Test error when right parenthesis is missing."""
        source = "func main( -> void { }"
        lexer = Lexer(source)
        parser = Parser(lexer)
        with self.assertRaises(ParseError):
            parser.parse()

    def test_missing_arrow(self):
        """Test error when arrow is missing."""
        source = "func main() void { }"
        lexer = Lexer(source)
        parser = Parser(lexer)
        with self.assertRaises(ParseError):
            parser.parse()

    def test_missing_return_type(self):
        """Test error when return type is missing."""
        source = "func main() -> { }"
        lexer = Lexer(source)
        parser = Parser(lexer)
        with self.assertRaises(ParseError):
            parser.parse()

    def test_missing_left_brace(self):
        """Test error when left brace is missing."""
        source = "func main() -> void }"
        lexer = Lexer(source)
        parser = Parser(lexer)
        with self.assertRaises(ParseError):
            parser.parse()

    def test_missing_right_brace(self):
        """Test error when right brace is missing."""
        source = "func main() -> void {"
        lexer = Lexer(source)
        parser = Parser(lexer)
        with self.assertRaises(ParseError):
            parser.parse()

    def test_missing_semicolon(self):
        """Test error when semicolon is missing."""
        source = "func main() -> void { let a int = 1 }"
        lexer = Lexer(source)
        parser = Parser(lexer)
        with self.assertRaises(ParseError):
            parser.parse()

    def test_missing_assignment_operator(self):
        """Test error when assignment operator is missing."""
        source = "func main() -> void { a int 1; }"
        lexer = Lexer(source)
        parser = Parser(lexer)
        with self.assertRaises(ParseError):
            parser.parse()

    def test_missing_expression_in_if(self):
        """Test error when expression in if is missing."""
        source = "func main() -> void { if () { } }"
        lexer = Lexer(source)
        parser = Parser(lexer)
        with self.assertRaises(ParseError):
            parser.parse()

    def test_missing_for_loop_semicolon(self):
        """Test error when semicolon in for loop is missing."""
        source = "func main() -> void { for (let i int = 0 i < 10; i = i + 1) { } }"
        lexer = Lexer(source)
        parser = Parser(lexer)
        with self.assertRaises(ParseError):
            parser.parse()

    def test_missing_for_loop_closing_paren(self):
        """Test error when closing paren in for loop is missing."""
        source = "func main() -> void { for (let i int = 0; i < 10; i = i + 1 { } }"
        lexer = Lexer(source)
        parser = Parser(lexer)
        with self.assertRaises(ParseError):
            parser.parse()

    def test_missing_function_call_closing_paren(self):
        """Test error when closing paren in function call is missing."""
        source = "func main() -> void { foo(1, 2; }"
        lexer = Lexer(source)
        parser = Parser(lexer)
        with self.assertRaises(ParseError):
            parser.parse()

    def test_unclosed_parentheses(self):
        """Test error when parentheses are not closed."""
        source = "func main() -> void { let a int = (1 + 2; }"
        lexer = Lexer(source)
        parser = Parser(lexer)
        with self.assertRaises(ParseError):
            parser.parse()


if __name__ == "__main__":
    unittest.main()
