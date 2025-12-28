from enum import Enum
from dataclasses import dataclass
from typing import Optional


class TokenType(Enum):
    # Keywords
    FUNC = "func"
    INT = "int"
    VOID = "void"
    LET = "let"
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
    LBRACKET = "["
    RBRACKET = "]"
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
            "let": TokenType.LET,
            "if": TokenType.IF,
            "else": TokenType.ELSE,
            "for": TokenType.FOR,
            "return": TokenType.RETURN,
            "break": TokenType.BREAK,
            "continue": TokenType.CONTINUE,
        }

    def _current_char(self) -> Optional[str]:
        if self.pos >= len(self.source):
            return None
        return self.source[self.pos]

    def _peek_char(self, offset: int = 1) -> Optional[str]:
        peek_pos = self.pos + offset
        if peek_pos >= len(self.source):
            return None
        return self.source[peek_pos]

    def _advance(self) -> Optional[str]:
        if self.pos >= len(self.source):
            return None

        char = self.source[self.pos]
        self.pos += 1

        if char == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1

        return char

    def _skip_whitespace(self):
        char = self._current_char()
        while char and char in " \t\r\n":
            self._advance()
            char = self._current_char()

    def _skip_comment(self):
        if self._current_char() == "/" and self._peek_char() == "/":
            # Skip both slashes
            self._advance()
            self._advance()
            # Skip until newline or EOF (support both \n and \r\n)
            while True:
                char = self._current_char()
                if char is None:
                    break
                if char == "\n":
                    self._advance()
                    break
                if char == "\r":
                    self._advance()
                    if self._current_char() == "\n":
                        self._advance()
                    break
                self._advance()

    def _read_integer(self) -> str:
        start_pos = self.pos
        char = self._current_char()
        while char and char.isdigit():
            self._advance()
            char = self._current_char()
        return self.source[start_pos : self.pos]

    def _read_identifier(self) -> str:
        start_pos = self.pos
        char = self._current_char()
        while char and (char.isalnum() or char == "_"):
            self._advance()
            char = self._current_char()
        return self.source[start_pos : self.pos]

    def _next_token(self) -> Token:
        # Skip whitespace and comments
        while True:
            self._skip_whitespace()
            if self._current_char() == "/" and self._peek_char() == "/":
                self._skip_comment()
            else:
                break

        # Check for EOF
        if self._current_char() is None:
            return Token(TokenType.EOF, "", self.line, self.column)

        line = self.line
        column = self.column

        char = self._current_char()

        if char == "(":
            self._advance()
            return Token(TokenType.LPAREN, "(", line, column)
        elif char == ")":
            self._advance()
            return Token(TokenType.RPAREN, ")", line, column)
        elif char == "{":
            self._advance()
            return Token(TokenType.LBRACE, "{", line, column)
        elif char == "}":
            self._advance()
            return Token(TokenType.RBRACE, "}", line, column)
        elif char == "[":
            self._advance()
            return Token(TokenType.LBRACKET, "[", line, column)
        elif char == "]":
            self._advance()
            return Token(TokenType.RBRACKET, "]", line, column)
        elif char == ";":
            self._advance()
            return Token(TokenType.SEMICOLON, ";", line, column)
        elif char == ",":
            self._advance()
            return Token(TokenType.COMMA, ",", line, column)
        elif char == "+":
            self._advance()
            return Token(TokenType.PLUS, "+", line, column)
        elif char == "*":
            self._advance()
            return Token(TokenType.MULTIPLY, "*", line, column)
        elif char == "/":
            self._advance()
            return Token(TokenType.DIVIDE, "/", line, column)
        elif char == "%":
            self._advance()
            return Token(TokenType.MODULO, "%", line, column)
        elif char == "!":
            self._advance()
            if self._current_char() == "=":
                self._advance()
                return Token(TokenType.NOT_EQUAL, "!=", line, column)
            return Token(TokenType.NOT, "!", line, column)

        elif char == "=":
            self._advance()
            if self._current_char() == "=":
                self._advance()
                return Token(TokenType.EQUAL, "==", line, column)
            return Token(TokenType.ASSIGN, "=", line, column)
        elif char == "<":
            self._advance()
            if self._current_char() == "=":
                self._advance()
                return Token(TokenType.LESS_EQUAL, "<=", line, column)
            return Token(TokenType.LESS, "<", line, column)
        elif char == ">":
            self._advance()
            if self._current_char() == "=":
                self._advance()
                return Token(TokenType.GREATER_EQUAL, ">=", line, column)
            return Token(TokenType.GREATER, ">", line, column)
        elif char == "&":
            self._advance()
            if self._current_char() == "&":
                self._advance()
                return Token(TokenType.AND, "&&", line, column)
            return Token(TokenType.ERROR, f"Unexpected character: &", line, column)
        elif char == "|":
            self._advance()
            if self._current_char() == "|":
                self._advance()
                return Token(TokenType.OR, "||", line, column)
            return Token(TokenType.ERROR, f"Unexpected character: |", line, column)
        elif char == "-":
            self._advance()
            if self._current_char() == ">":
                self._advance()
                return Token(TokenType.ARROW, "->", line, column)
            return Token(TokenType.MINUS, "-", line, column)

        elif char and char.isdigit():
            value = self._read_integer()
            return Token(TokenType.INTEGER, value, line, column)

        elif char and (char.isalpha() or char == "_"):
            value = self._read_identifier()
            token_type = self.keywords.get(value, TokenType.IDENTIFIER)
            return Token(token_type, value, line, column)

        else:
            self._advance()
            return Token(TokenType.ERROR, f"Unexpected character: {char}", line, column)

    def tokenize(self) -> list[Token]:
        """Tokenize the entire source code."""
        tokens = []
        while True:
            token = self._next_token()
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
