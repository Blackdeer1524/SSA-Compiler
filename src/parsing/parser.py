from abc import ABC
from dataclasses import dataclass, field
from typing import Optional, List, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from .semantic import SymbolTable

from .lexer import Lexer, Token, TokenType


# AST Node classes
@dataclass
class ASTNode(ABC):
    line: int
    column: int


@dataclass
class Program(ASTNode):
    line: int = field(init=False, default=1)
    column: int = field(init=False, default=1)

    functions: List["Function"]
    symbol_table: Optional["SymbolTable"] = None


@dataclass
class Function(ASTNode):
    name: str
    args: List["Argument"]
    return_type: str
    body: "Block"


@dataclass
class Argument(ASTNode):
    name: str
    type: str


@dataclass
class Statement(ASTNode):
    pass


@dataclass
class Assignment(Statement):
    name: str
    type: str
    value: "Expression"


@dataclass
class Reassignment(Statement):
    lvalue: "LValue"
    value: "Expression"


@dataclass
class Condition(Statement):
    condition: "Expression"
    then_block: "Block"
    else_block: Optional["Block"]


@dataclass
class ForLoop(Statement):
    init: list[Assignment]
    condition: "Expression"
    update: list[Reassignment]
    body: "Block"


@dataclass
class UnconditionalLoop(Statement):
    body: "Block"


@dataclass
class FunctionCall(Statement):
    name: str
    args: List["Expression"]


@dataclass
class Return(Statement):
    value: Optional["Expression"]


@dataclass
class Break(Statement):
    line: int
    column: int


@dataclass
class Continue(Statement):
    line: int
    column: int


@dataclass
class Block:
    statements: List[Statement]
    symbol_table: Optional["SymbolTable"] = None


@dataclass
class Expression(ASTNode):
    pass


@dataclass
class BinaryOp(Expression):
    operator: str
    left: Expression
    right: Expression


@dataclass
class UnaryOp(Expression):
    operator: str
    operand: Expression


@dataclass
class Identifier(Expression):
    name: str


@dataclass
class IntegerLiteral(Expression):
    value: int


@dataclass
class CallExpression(Expression):
    name: str
    args: List[Expression]


@dataclass
class ArrayAccess(Expression):
    base: Identifier
    indices: List[Expression]


@dataclass
class ArrayInit(Expression):
    pass


@dataclass
class LValue(ASTNode):
    """Left-hand side value for assignments - can be identifier or array access."""


@dataclass
class LValueIdentifier(LValue):
    name: str


@dataclass
class LValueArrayAccess(LValue):
    base: str  # Base variable name
    indices: List[Expression]


class ParseError(Exception):
    def __init__(self, message: str, token: Optional[Token] = None):
        self.message = message
        self.token = token
        if token:
            super().__init__(f"{message} at line {token.line}, column {token.column}")
        else:
            super().__init__(message)


class Parser:
    def __init__(self, lexer: Lexer):
        self.lexer = lexer
        self.tokens = lexer.tokenize()
        self.pos = 0
        self.current_token = self.tokens[0] if self.tokens else None

    def advance(self):
        self.pos += 1
        if self.pos < len(self.tokens):
            self.current_token = self.tokens[self.pos]
        else:
            self.current_token = None

    def expect(self, token_type: TokenType) -> Token:
        if not self.current_token:
            raise ParseError(f"Expected {token_type.name}, but reached end of file")

        if self.current_token.type != token_type:
            raise ParseError(
                f"Expected {token_type.name}, but got {self.current_token.type.name}",
                self.current_token,
            )

        token = self.current_token
        self.advance()
        return token

    def check(self, token_type: TokenType) -> bool:
        return self.current_token is not None and self.current_token.type == token_type

    def match(self, *token_types: TokenType) -> bool:
        return self.current_token is not None and self.current_token.type in token_types

    # Grammar rules implementation

    def parse(self) -> Program:
        """
        PROGRAMM ::= FUNCTION+ EOF
        """
        functions = []
        functions.append(self.parse_function())
        while self.current_token and self.current_token.type != TokenType.EOF:
            functions.append(self.parse_function())
        return Program(functions)

    def parse_function(self) -> Function:
        """
        FUNCTION ::= "func" IDENTIFIER "(" ARG_LIST ")" "->" TYPE BLOCK
        """
        self.expect(TokenType.FUNC)

        name_token = self.expect(TokenType.IDENTIFIER)
        name = name_token.value
        line = name_token.line
        column = name_token.column

        self.expect(TokenType.LPAREN)
        args = self.parse_arg_list()
        self.expect(TokenType.RPAREN)

        self.expect(TokenType.ARROW)
        return_type = self.parse_type()

        body = self.parse_block()

        return Function(line, column, name, args, return_type, body)

    def parse_arg_list(self) -> List[Argument]:
        """ARG_LIST ::= EPSILON | ARG ("," ARG)*"""
        args = []
        if self.check(TokenType.IDENTIFIER):
            args.append(self.parse_arg())
            while self.check(TokenType.COMMA):
                self.advance()  # consume comma
                args.append(self.parse_arg())
        return args

    def parse_arg(self) -> Argument:
        """ARG ::= IDENTIFIER TYPE"""
        name_token = self.expect(TokenType.IDENTIFIER)
        name = name_token.value

        arg_type = self.parse_type()
        return Argument(name_token.line, name_token.column, name, arg_type)

    def parse_type(self) -> str:
        """TYPE ::= int | ("[" INTEGER "]")+ int | void"""
        dimensions = []
        while self.check(TokenType.LBRACKET):
            self.advance()  # consume '['
            if not self.check(TokenType.INTEGER):
                raise ParseError(
                    "Expected integer in array dimension", self.current_token
                )
            dim_token = self.expect(TokenType.INTEGER)
            dimensions.append(int(dim_token.value))
            self.expect(TokenType.RBRACKET)  # consume ']'

        if self.check(TokenType.INT):
            self.advance()
            base_type = "int"
        elif self.check(TokenType.VOID):
            self.advance()
            base_type = "void"
        else:
            raise ParseError("Expected 'int' or 'void'", self.current_token)

        if dimensions:
            dims_str = "".join(f"[{d}]" for d in dimensions)
            return f"{dims_str}{base_type}"
        else:
            return base_type

    def parse_statements(self) -> List[Statement]:
        """STATEMENTS ::= STATEMENT*"""
        statements = []
        while self.current_token and not self.check(TokenType.RBRACE):
            statements.append(self.parse_statement())
        return statements

    def parse_statement(self) -> Statement:
        """STATEMENT ::= ASSIGNMENT ";" | REASSIGNMENT ";" | CONDITION | LOOP | FUNCTION_CALL ";" | RETURN ";" | BLOCK"""
        if not self.current_token:
            raise ParseError("Unexpected end of file")

        token = self.current_token

        if self.check(TokenType.IF):
            return self.parse_condition()

        if self.check(TokenType.FOR):
            return self.parse_loop()

        if self.check(TokenType.RETURN):
            return self.parse_return()

        if self.check(TokenType.BREAK):
            return self.parse_break()

        if self.check(TokenType.CONTINUE):
            return self.parse_continue()

        if self.check(TokenType.LET):
            assignment = self.parse_assignment()
            self.expect(TokenType.SEMICOLON)
            return assignment

        if self.check(TokenType.IDENTIFIER):
            if self.pos + 1 < len(self.tokens):
                next_token = self.tokens[self.pos + 1]

                if next_token.type == TokenType.LPAREN:
                    call = self.parse_function_call()
                    self.expect(TokenType.SEMICOLON)
                    return call
                elif next_token.type == TokenType.ASSIGN:
                    reassignment = self.parse_reassignment()
                    self.expect(TokenType.SEMICOLON)
                    return reassignment
                elif next_token.type == TokenType.LBRACKET:
                    peek_pos = self.pos + 1
                    bracket_count = 0
                    found_assign = False
                    while peek_pos < len(self.tokens):
                        tok = self.tokens[peek_pos]
                        if tok.type == TokenType.LBRACKET:
                            bracket_count += 1
                        elif tok.type == TokenType.RBRACKET:
                            bracket_count -= 1
                        elif tok.type == TokenType.ASSIGN and bracket_count == 0:
                            found_assign = True
                            break
                        elif tok.type in (
                            TokenType.SEMICOLON,
                            TokenType.EOF,
                            TokenType.RBRACE,
                        ):
                            break
                        peek_pos += 1

                    if found_assign:
                        reassignment = self.parse_reassignment()
                        self.expect(TokenType.SEMICOLON)
                        return reassignment

        raise ParseError(f"Unexpected token: {token.type.name}", token)

    def parse_assignment(self) -> Assignment:
        """ASSIGNMENT ::= "let" IDENTIFIER TYPE "=" EXPR"""
        self.expect(TokenType.LET)

        name_token = self.expect(TokenType.IDENTIFIER)
        name = name_token.value
        line = name_token.line
        column = name_token.column

        var_type = self.parse_type()

        self.expect(TokenType.ASSIGN)

        # Check for array initialization: {}
        if self.check(TokenType.LBRACE):
            lbrace = self.expect(TokenType.LBRACE)
            self.expect(TokenType.RBRACE)  # consume '}'
            value = ArrayInit(lbrace.line, lbrace.column)
        else:
            value = self.parse_expr()

        return Assignment(line, column, name, var_type, value)

    def parse_reassignment(self) -> Reassignment:
        """REASSIGNMENT ::= EXPR_LVALUE "=" EXPR"""
        lvalue = self.parse_lvalue()
        line = lvalue.line if hasattr(lvalue, "line") else 0
        column = lvalue.column if hasattr(lvalue, "column") else 0

        self.expect(TokenType.ASSIGN)
        value = self.parse_expr()
        return Reassignment(line, column, lvalue, value)

    def parse_lvalue(self) -> "LValue":
        """EXPR_LVALUE ::= IDENTIFIER ("[" EXPR "]")*"""
        name_token = self.expect(TokenType.IDENTIFIER)
        base_name = name_token.value
        line = name_token.line
        column = name_token.column

        # Check for array indexing
        indices = []
        while self.check(TokenType.LBRACKET):
            self.advance()  # consume '['
            index_expr = self.parse_expr()
            indices.append(index_expr)
            self.expect(TokenType.RBRACKET)  # consume ']'

        if indices:
            return LValueArrayAccess(line, column, base_name, indices)
        else:
            return LValueIdentifier(line, column, base_name)

    def parse_condition(self) -> Condition:
        """CONDITION ::= if "(" EXPR ")" BLOCK [else BLOCK]"""
        if_token = self.expect(TokenType.IF)
        line = if_token.line
        column = if_token.column

        self.expect(TokenType.LPAREN)
        condition = self.parse_expr()
        self.expect(TokenType.RPAREN)

        then_block = self.parse_block()

        else_block = None
        if self.check(TokenType.ELSE):
            self.advance()
            else_block = self.parse_block()

        return Condition(line, column, condition, then_block, else_block)

    def parse_loop(self) -> Union["ForLoop", "UnconditionalLoop"]:
        """LOOP ::= for BLOCK | for "(" ASSIGNMENT ("," ASSIGNMENT)* ";" EXPR ";" REASSIGNMENT ("," REASSIGNMENT)* ")" BLOCK"""
        for_token = self.expect(TokenType.FOR)
        line = for_token.line
        column = for_token.column

        if self.check(TokenType.LBRACE):
            body = self.parse_block()
            return UnconditionalLoop(line, column, body)

        self.expect(TokenType.LPAREN)
        init = [self.parse_assignment()]
        while self.check(TokenType.COMMA):
            self.advance()
            init.append(self.parse_assignment())

        self.expect(TokenType.SEMICOLON)
        condition = self.parse_expr()
        self.expect(TokenType.SEMICOLON)

        update = [self.parse_reassignment()]
        while self.check(TokenType.COMMA):
            self.advance()
            update.append(self.parse_reassignment())
        self.expect(TokenType.RPAREN)
        body = self.parse_block()

        return ForLoop(line, column, init, condition, update, body)

    def parse_function_call(self) -> FunctionCall:
        """FUNCTION_CALL ::= IDENTIFIER "(" EXPR_LIST ")" """
        name_token = self.expect(TokenType.IDENTIFIER)
        name = name_token.value
        line = name_token.line
        column = name_token.column

        self.expect(TokenType.LPAREN)
        args = self.parse_expr_list()
        self.expect(TokenType.RPAREN)

        return FunctionCall(line, column, name, args)

    def parse_expr_list(self) -> List[Expression]:
        """EXPR_LIST ::= EPSILON | EXPR ("," EXPR)*"""
        args = []
        if not self.check(TokenType.RPAREN):
            args.append(self.parse_expr())
            while self.check(TokenType.COMMA):
                self.advance()  # consume comma
                args.append(self.parse_expr())
        return args

    def parse_return(self) -> Return:
        """RETURN ::= return [EXPR]"""
        return_token = self.expect(TokenType.RETURN)
        line = return_token.line
        column = return_token.column

        value = None
        if not self.check(TokenType.SEMICOLON):
            value = self.parse_expr()

        self.expect(TokenType.SEMICOLON)
        return Return(line, column, value)

    def parse_break(self) -> Break:
        """BREAK ::= break ;"""
        break_token = self.expect(TokenType.BREAK)
        line = break_token.line
        column = break_token.column

        self.expect(TokenType.SEMICOLON)
        return Break(line, column)

    def parse_continue(self) -> Continue:
        """CONTINUE ::= continue ";" """
        continue_token = self.expect(TokenType.CONTINUE)
        line = continue_token.line
        column = continue_token.column

        self.expect(TokenType.SEMICOLON)
        return Continue(line, column)

    def parse_block(self) -> Block:
        """BLOCK ::= "{" STATEMENTS "}" """
        self.expect(TokenType.LBRACE)
        statements = self.parse_statements()
        self.expect(TokenType.RBRACE)
        return Block(statements)

    # Expression parsing with operator precedence
    def parse_expr(self) -> Expression:
        """EXPR ::= EXPR_OR"""
        return self.parse_expr_or()

    def parse_expr_or(self) -> Expression:
        """EXPR_OR ::= EXPR_AND ("||" EXPR_AND)*"""
        left = self.parse_expr_and()
        while self.check(TokenType.OR):
            or_token = self.expect(TokenType.OR)
            right = self.parse_expr_and()
            left = BinaryOp(or_token.line, or_token.column, "||", left, right)
        return left

    def parse_expr_and(self) -> Expression:
        """EXPR_AND ::= EXPR_COMP ("&&" EXPR_COMP)*"""
        left = self.parse_expr_comp()
        while self.check(TokenType.AND):
            and_token = self.expect(TokenType.AND)
            right = self.parse_expr_comp()
            left = BinaryOp(and_token.line, and_token.column, "&&", left, right)
        return left

    def parse_expr_comp(self) -> Expression:
        """EXPR_COMP ::= EXPR_ADD (("==" | "!=" | "<" | "<=" | ">" | ">=") EXPR_ADD)*"""
        left = self.parse_expr_add()
        while self.match(
            TokenType.EQUAL,
            TokenType.NOT_EQUAL,
            TokenType.LESS,
            TokenType.LESS_EQUAL,
            TokenType.GREATER,
            TokenType.GREATER_EQUAL,
        ):
            if self.current_token is None:
                break
            op_token = self.current_token
            self.advance()
            right = self.parse_expr_add()
            op_str = op_token.value
            left = BinaryOp(op_token.line, op_token.column, op_str, left, right)
        return left

    def parse_expr_add(self) -> Expression:
        """EXPR_ADD ::= EXPR_MUL (("+" | "-") EXPR_MUL)*"""
        left = self.parse_expr_mul()
        while self.match(TokenType.PLUS, TokenType.MINUS):
            if self.current_token is None:
                break
            op_token = self.current_token
            self.advance()
            op_str = op_token.value
            right = self.parse_expr_mul()
            left = BinaryOp(op_token.line, op_token.column, op_str, left, right)
        return left

    def parse_expr_mul(self) -> Expression:
        """EXPR_MUL ::= EXPR_UNARY (("*" | "/" | "%") EXPR_UNARY)*"""
        left = self.parse_expr_unary()
        while self.match(TokenType.MULTIPLY, TokenType.DIVIDE, TokenType.MODULO):
            if self.current_token is None:
                break
            op_token = self.current_token
            self.advance()
            op_str = op_token.value
            right = self.parse_expr_unary()
            left = BinaryOp(op_token.line, op_token.column, op_str, left, right)
        return left

    def parse_expr_unary(self) -> Expression:
        """EXPR_UNARY ::= EXPR_ATOM | "-" EXPR_UNARY | "!" EXPR_UNARY"""
        if self.check(TokenType.MINUS):
            minus_token = self.expect(TokenType.MINUS)
            operand = self.parse_expr_unary()
            return UnaryOp(minus_token.line, minus_token.column, "-", operand)
        elif self.check(TokenType.NOT):
            not_token = self.expect(TokenType.NOT)
            operand = self.parse_expr_unary()
            return UnaryOp(not_token.line, not_token.column, "!", operand)
        else:
            return self.parse_expr_atom()

    def parse_expr_atom(self) -> Expression:
        """EXPR_ATOM ::= IDENTIFIER ("[" EXPR "]")* | INTEGER | "(" EXPR ")" | FUNCTION_CALL"""
        if self.check(TokenType.INTEGER):
            token = self.expect(TokenType.INTEGER)
            return IntegerLiteral(token.line, token.column, int(token.value))
        elif self.check(TokenType.IDENTIFIER):
            # Check if it's a function call
            if (
                self.pos + 1 < len(self.tokens)
                and self.tokens[self.pos + 1].type == TokenType.LPAREN
            ):
                name_token = self.expect(TokenType.IDENTIFIER)
                name = name_token.value
                self.expect(TokenType.LPAREN)
                args = self.parse_expr_list()
                self.expect(TokenType.RPAREN)
                return CallExpression(name_token.line, name_token.column, name, args)
            else:
                name_token = self.expect(TokenType.IDENTIFIER)
                base = Identifier(name_token.line, name_token.column, name_token.value)

                indices = []
                while self.check(TokenType.LBRACKET):
                    self.advance()  # consume '['
                    index_expr = self.parse_expr()
                    indices.append(index_expr)
                    self.expect(TokenType.RBRACKET)  # consume ']'

                if indices:
                    return ArrayAccess(
                        name_token.line, name_token.column, base, indices
                    )
                else:
                    return base
        elif self.check(TokenType.LPAREN):
            self.advance()
            expr = self.parse_expr()
            self.expect(TokenType.RPAREN)
            return expr
        else:
            raise ParseError("Expected expression", self.current_token)


if __name__ == "__main__":
    test_code = """func main() -> void {
    a int = 1;
    b int = 2 + (-a);
    if (i < 10) {
        a int = 20;
    }
    for (i int = 0; i < 10; i = i + 1) {
    }
    foo(1, 2);
    if (i <= 10 || i > 40 && i + 2 < i - 1) {
    } else {
    }
    return 1 + 2;
}"""

    from .lexer import Lexer

    lexer = Lexer(test_code)
    parser = Parser(lexer)

    try:
        ast = parser.parse()
        print("Parse successful!")
        print(f"Found {len(ast.functions)} function(s)")
        for func in ast.functions:
            print(f"  - {func.name}() -> {func.return_type}")
    except ParseError as e:
        print(f"Parse error: {e}")
