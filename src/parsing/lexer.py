from enum import Enum
from dataclasses import dataclass
from typing import Optional


class TokenType(Enum):
    # Keywords
    FUNC = "func"
    INT = "int"
    VOID = "void"
    IF = "if"
    ELSE = "else"
    FOR = "for"
    RETURN = "return"
    BREAK = "break"
    CONTINUE = "continue"
    
    # Identifiers and literals
    IDENTIFIER = "identifier"
    INTEGER = "integer"
    
    # Operators
    PLUS = "+"
    MINUS = "-"
    MULTIPLY = "*"
    DIVIDE = "/"
    MODULO = "%"
    EQUAL = "=="
    NOT_EQUAL = "!="
    LESS = "<"
    LESS_EQUAL = "<="
    GREATER = ">"
    GREATER_EQUAL = ">="
    AND = "&&"
    OR = "||"
    NOT = "!"
    ASSIGN = "="
    ARROW = "->"
    
    # Punctuation
    LPAREN = "("
    RPAREN = ")"
    LBRACE = "{"
    RBRACE = "}"
    SEMICOLON = ";"
    COMMA = ","
    
    # Special
    EOF = "EOF"
    ERROR = "ERROR"


@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    column: int
    
    def __repr__(self):
        return f"Token({self.type.name}, {self.value!r}, line={self.line}, col={self.column})"


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.column = 1
        self.keywords = {
            "func": TokenType.FUNC,
            "int": TokenType.INT,
            "void": TokenType.VOID,
            "if": TokenType.IF,
            "else": TokenType.ELSE,
            "for": TokenType.FOR,
            "return": TokenType.RETURN,
            "break": TokenType.BREAK,
            "continue": TokenType.CONTINUE,
        }
    
    def current_char(self) -> Optional[str]:
        if self.pos >= len(self.source):
            return None
        return self.source[self.pos]
    
    def peek_char(self, offset: int = 1) -> Optional[str]:
        peek_pos = self.pos + offset
        if peek_pos >= len(self.source):
            return None
        return self.source[peek_pos]
    
    def advance(self) -> Optional[str]:
        if self.pos >= len(self.source):
            return None
        
        char = self.source[self.pos]
        self.pos += 1
        
        if char == '\n':
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        
        return char
    
    def skip_whitespace(self):
        char = self.current_char()
        while char and char in ' \t\r\n':
            self.advance()
            char = self.current_char()
    
    def skip_comment(self):
        if self.current_char() == '/' and self.peek_char() == '/':
            # Skip both slashes
            self.advance()
            self.advance()
            # Skip until newline or EOF (support both \n and \r\n)
            while True:
                char = self.current_char()
                if char is None:
                    break
                if char == '\n':
                    self.advance()
                    break
                if char == '\r':
                    self.advance()
                    if self.current_char() == '\n':
                        self.advance()
                    break
                self.advance()
    
    def read_integer(self) -> str:
        start_pos = self.pos
        char = self.current_char()
        while char and char.isdigit():
            self.advance()
            char = self.current_char()
        return self.source[start_pos:self.pos]
    
    def read_identifier(self) -> str:
        start_pos = self.pos
        char = self.current_char()
        while char and (char.isalnum() or char == '_'):
            self.advance()
            char = self.current_char()
        return self.source[start_pos:self.pos]
    
    def next_token(self) -> Token:
        # Skip whitespace and comments
        while True:
            self.skip_whitespace()
            if self.current_char() == '/' and self.peek_char() == '/':
                self.skip_comment()
            else:
                break
        
        # Check for EOF
        if self.current_char() is None:
            return Token(TokenType.EOF, "", self.line, self.column)
        
        line = self.line
        column = self.column
        
        char = self.current_char()
        
        if char == '(':
            self.advance()
            return Token(TokenType.LPAREN, "(", line, column)
        elif char == ')':
            self.advance()
            return Token(TokenType.RPAREN, ")", line, column)
        elif char == '{':
            self.advance()
            return Token(TokenType.LBRACE, "{", line, column)
        elif char == '}':
            self.advance()
            return Token(TokenType.RBRACE, "}", line, column)
        elif char == ';':
            self.advance()
            return Token(TokenType.SEMICOLON, ";", line, column)
        elif char == ',':
            self.advance()
            return Token(TokenType.COMMA, ",", line, column)
        elif char == '+':
            self.advance()
            return Token(TokenType.PLUS, "+", line, column)
        elif char == '*':
            self.advance()
            return Token(TokenType.MULTIPLY, "*", line, column)
        elif char == '/':
            self.advance()
            return Token(TokenType.DIVIDE, "/", line, column)
        elif char == '%':
            self.advance()
            return Token(TokenType.MODULO, "%", line, column)
        elif char == '!':
            self.advance()
            if self.current_char() == '=':
                self.advance()
                return Token(TokenType.NOT_EQUAL, "!=", line, column)
            return Token(TokenType.NOT, "!", line, column)
        
        elif char == '=':
            self.advance()
            if self.current_char() == '=':
                self.advance()
                return Token(TokenType.EQUAL, "==", line, column)
            return Token(TokenType.ASSIGN, "=", line, column)
        elif char == '<':
            self.advance()
            if self.current_char() == '=':
                self.advance()
                return Token(TokenType.LESS_EQUAL, "<=", line, column)
            return Token(TokenType.LESS, "<", line, column)
        elif char == '>':
            self.advance()
            if self.current_char() == '=':
                self.advance()
                return Token(TokenType.GREATER_EQUAL, ">=", line, column)
            return Token(TokenType.GREATER, ">", line, column)
        elif char == '&':
            self.advance()
            if self.current_char() == '&':
                self.advance()
                return Token(TokenType.AND, "&&", line, column)
            return Token(TokenType.ERROR, f"Unexpected character: &", line, column)
        elif char == '|':
            self.advance()
            if self.current_char() == '|':
                self.advance()
                return Token(TokenType.OR, "||", line, column)
            return Token(TokenType.ERROR, f"Unexpected character: |", line, column)
        elif char == '-':
            self.advance()
            if self.current_char() == '>':
                self.advance()
                return Token(TokenType.ARROW, "->", line, column)
            return Token(TokenType.MINUS, "-", line, column)
        
        elif char and char.isdigit():
            value = self.read_integer()
            return Token(TokenType.INTEGER, value, line, column)
        
        elif char and (char.isalpha() or char == '_'):
            value = self.read_identifier()
            token_type = self.keywords.get(value, TokenType.IDENTIFIER)
            return Token(token_type, value, line, column)
        
        else:
            self.advance()
            return Token(TokenType.ERROR, f"Unexpected character: {char}", line, column)
    
    def tokenize(self) -> list[Token]:
        """Tokenize the entire source code."""
        tokens = []
        while True:
            token = self.next_token()
            tokens.append(token)
            if token.type == TokenType.EOF:
                break
        return tokens


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
    
    lexer = Lexer(test_code)
    tokens = lexer.tokenize()
    
    for token in tokens:
        print(token)

