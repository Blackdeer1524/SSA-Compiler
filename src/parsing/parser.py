from dataclasses import dataclass, field
from typing import Optional, List, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from .semantic import SymbolTable

from .lexer import Lexer, Token, TokenType


# AST Node classes
@dataclass
class ASTNode:
    """Base class for AST nodes."""
    pass


@dataclass
class Program(ASTNode):
    functions: List['Function']
    symbol_table: Optional['SymbolTable'] = None


@dataclass
class Function(ASTNode):
    name: str
    args: List['Argument']
    return_type: str
    body: 'Block'
    line: int
    column: int


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
    value: 'Expression'
    line: int
    column: int


@dataclass
class Reassignment(Statement):
    name: str
    value: 'Expression'
    line: int
    column: int


@dataclass
class Condition(Statement):
    condition: 'Expression'
    then_block: 'Block'
    else_block: Optional['Block']
    line: int
    column: int  


@dataclass
class ForLoop(Statement):
    init: Assignment
    condition: 'Expression'
    update: Reassignment
    body: 'Block'
    line: int
    column: int  


@dataclass
class UnconditionalLoop(Statement):
    body: 'Block'
    line: int
    column: int 


@dataclass
class FunctionCall(Statement):
    name: str
    args: List['Expression']
    line: int
    column: int


@dataclass
class Return(Statement):
    value: Optional['Expression']
    line: int
    column: int


@dataclass
class Break(Statement):
    line: int
    column: int


@dataclass
class Continue(Statement):
    line: int
    column: int


@dataclass
class Block(Statement):
    statements: List[Statement]
    symbol_table: Optional['SymbolTable'] = None 


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
                self.current_token
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
        functions = []
        while self.current_token and self.current_token.type != TokenType.EOF:
            functions.append(self.parse_function())
        return Program(functions)
    
    def parse_function(self) -> Function:
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
        
        return Function(name, args, return_type, body, line, column)
    
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
        """ARG ::= %name% %type%"""
        name_token = self.expect(TokenType.IDENTIFIER)
        name = name_token.value
        
        type_token = self.expect(TokenType.INT)  # Only int is supported for now
        arg_type = type_token.value
        
        return Argument(name, arg_type)
    
    def parse_type(self) -> str:
        """TYPE ::= int | void"""
        if self.check(TokenType.INT):
            self.advance()
            return "int"
        elif self.check(TokenType.VOID):
            self.advance()
            return "void"
        else:
            raise ParseError("Expected 'int' or 'void'", self.current_token)
    
    def parse_statements(self) -> List[Statement]:
        """STATEMENTS ::= STATEMENT*"""
        statements = []
        while self.current_token and not self.check(TokenType.RBRACE):
            statements.append(self.parse_statement())
        return statements
    
    def parse_statement(self) -> Statement:
        """STATEMENT ::= ASSIGNMENT | REASSIGNMENT | CONDITION | LOOP | FUNCTION_CALL ";" | RETURN ";" | BLOCK"""
        if not self.current_token:
            raise ParseError("Unexpected end of file")
        
        token = self.current_token
        
        # BLOCK
        if self.check(TokenType.LBRACE):
            return self.parse_block()
        
        # CONDITION
        if self.check(TokenType.IF):
            return self.parse_condition()
        
        # LOOP
        if self.check(TokenType.FOR):
            return self.parse_loop()
        
        # RETURN
        if self.check(TokenType.RETURN):
            return self.parse_return()
        
        # BREAK
        if self.check(TokenType.BREAK):
            return self.parse_break()
        
        # CONTINUE
        if self.check(TokenType.CONTINUE):
            return self.parse_continue()
        
        # ASSIGNMENT or REASSIGNMENT or FUNCTION_CALL
        if self.check(TokenType.IDENTIFIER):
            # Peek ahead to distinguish between assignment, reassignment, and function call
            if self.pos + 1 < len(self.tokens):
                next_token = self.tokens[self.pos + 1]
                
                # ASSIGNMENT: identifier int = ...
                if next_token.type == TokenType.INT:
                    return self.parse_assignment()
                # FUNCTION_CALL: identifier ( ...
                elif next_token.type == TokenType.LPAREN:
                    call = self.parse_function_call()
                    self.expect(TokenType.SEMICOLON)
                    return call
                # REASSIGNMENT: identifier = ...
                elif next_token.type == TokenType.ASSIGN:
                    return self.parse_reassignment()
        
        raise ParseError(f"Unexpected token: {token.type.name}", token)
    
    def parse_assignment(self) -> Assignment:
        """ASSIGNMENT ::= %name% %type% "=" EXPR ";" """
        name_token = self.expect(TokenType.IDENTIFIER)
        name = name_token.value
        line = name_token.line
        column = name_token.column
        
        type_token = self.expect(TokenType.INT)
        var_type = type_token.value
        
        self.expect(TokenType.ASSIGN)
        value = self.parse_expr()
        self.expect(TokenType.SEMICOLON)
        
        return Assignment(name, var_type, value, line, column)
    
    def parse_reassignment(self, require_semicolon: bool = True) -> Reassignment:
        """REASSIGNMENT ::= %name% "=" EXPR [";"] """
        name_token = self.expect(TokenType.IDENTIFIER)
        name = name_token.value
        line = name_token.line
        column = name_token.column
        
        self.expect(TokenType.ASSIGN)
        value = self.parse_expr()
        if require_semicolon:
            self.expect(TokenType.SEMICOLON)
        
        return Reassignment(name, value, line, column)
    
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
        
        return Condition(condition, then_block, else_block, line, column)
    
    def parse_loop(self) -> Union['ForLoop', 'UnconditionalLoop']:
        """LOOP ::= for BLOCK | for "(" ASSIGNMENT ";" EXPR ";" REASSIGNMENT ")" BLOCK"""
        for_token = self.expect(TokenType.FOR)
        line = for_token.line
        column = for_token.column
        
        # Unconditional loop: for BLOCK
        if self.check(TokenType.LBRACE):
            body = self.parse_block()
            return UnconditionalLoop(body, line, column)
        
        # for loop: for (ASSIGNMENT; EXPR; REASSIGNMENT) BLOCK
        self.expect(TokenType.LPAREN)
        init = self.parse_assignment()  # This already consumes the semicolon
        condition = self.parse_expr()
        self.expect(TokenType.SEMICOLON)
        update = self.parse_reassignment(require_semicolon=False)  # No semicolon in for loop
        self.expect(TokenType.RPAREN)
        body = self.parse_block()
        
        return ForLoop(init, condition, update, body, line, column)
    
    def parse_function_call(self) -> FunctionCall:
        """FUNCTION_CALL ::= %name% "(" EXPR_LIST ")" """
        name_token = self.expect(TokenType.IDENTIFIER)
        name = name_token.value
        line = name_token.line
        column = name_token.column
        
        self.expect(TokenType.LPAREN)
        args = self.parse_expr_list()
        self.expect(TokenType.RPAREN)
        
        return FunctionCall(name, args, line, column)
    
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
        return Return(value, line, column)
    
    def parse_break(self) -> Break:
        """BREAK ::= break ;"""
        break_token = self.expect(TokenType.BREAK)
        line = break_token.line
        column = break_token.column
        
        self.expect(TokenType.SEMICOLON)
        return Break(line, column)
    
    def parse_continue(self) -> Continue:
        """CONTINUE ::= continue ;"""
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
            op_token = self.advance()
            right = self.parse_expr_and()
            left = BinaryOp("||", left, right)
        return left
    
    def parse_expr_and(self) -> Expression:
        """EXPR_AND ::= EXPR_COMP ("&&" EXPR_COMP)*"""
        left = self.parse_expr_comp()
        while self.check(TokenType.AND):
            op_token = self.advance()
            right = self.parse_expr_comp()
            left = BinaryOp("&&", left, right)
        return left
    
    def parse_expr_comp(self) -> Expression:
        """EXPR_COMP ::= EXPR_ADD (("==" | "!=" | "<" | "<=" | ">" | ">=") EXPR_ADD)*"""
        left = self.parse_expr_add()
        while self.match(TokenType.EQUAL, TokenType.NOT_EQUAL, TokenType.LESS, 
                        TokenType.LESS_EQUAL, TokenType.GREATER, TokenType.GREATER_EQUAL):
            if self.current_token is None:
                break
            op_token = self.current_token
            self.advance()
            right = self.parse_expr_add()
            op_str = op_token.value
            left = BinaryOp(op_str, left, right)
        return left
    
    def parse_expr_add(self) -> Expression:
        """EXPR_ADD ::= EXPR_MUL (("+" | "-") EXPR_MUL)*"""
        left = self.parse_expr_mul()
        while self.match(TokenType.PLUS, TokenType.MINUS):
            if self.current_token is None:
                break
            op_token = self.current_token
            self.advance()
            right = self.parse_expr_mul()
            op_str = op_token.value
            left = BinaryOp(op_str, left, right)
        return left
    
    def parse_expr_mul(self) -> Expression:
        """EXPR_MUL ::= EXPR_UNARY (("*" | "/" | "%") EXPR_UNARY)*"""
        left = self.parse_expr_unary()
        while self.match(TokenType.MULTIPLY, TokenType.DIVIDE, TokenType.MODULO):
            if self.current_token is None:
                break
            op_token = self.current_token
            self.advance()
            right = self.parse_expr_unary()
            op_str = op_token.value
            left = BinaryOp(op_str, left, right)
        return left
    
    def parse_expr_unary(self) -> Expression:
        """EXPR_UNARY ::= EXPR_ATOM | "-" EXPR_UNARY | "!" EXPR_UNARY"""
        if self.check(TokenType.MINUS):
            self.advance()
            operand = self.parse_expr_unary()
            return UnaryOp("-", operand)
        elif self.check(TokenType.NOT):
            self.advance()
            operand = self.parse_expr_unary()
            return UnaryOp("!", operand)
        else:
            return self.parse_expr_atom()
    
    def parse_expr_atom(self) -> Expression:
        """EXPR_ATOM ::= %name% | %integer% | "(" EXPR ")" | FUNCTION_CALL"""
        if self.check(TokenType.INTEGER):
            token = self.expect(TokenType.INTEGER)
            return IntegerLiteral(int(token.value))
        elif self.check(TokenType.IDENTIFIER):
            # Check if it's a function call
            if self.pos + 1 < len(self.tokens) and self.tokens[self.pos + 1].type == TokenType.LPAREN:
                name_token = self.expect(TokenType.IDENTIFIER)
                name = name_token.value
                self.expect(TokenType.LPAREN)
                args = self.parse_expr_list()
                self.expect(TokenType.RPAREN)
                return CallExpression(name, args)
            else:
                token = self.expect(TokenType.IDENTIFIER)
                return Identifier(token.value)
        elif self.check(TokenType.LPAREN):
            self.advance()
            expr = self.parse_expr()
            self.expect(TokenType.RPAREN)
            return expr
        else:
            raise ParseError("Expected expression", self.current_token)


if __name__ == "__main__":
    # Test the parser
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

