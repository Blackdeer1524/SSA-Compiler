import unittest
from src.parsing.lexer import Lexer, Token, TokenType


class TestLexer(unittest.TestCase):
    """Unit tests for the Lexer class."""
    
    def test_empty_input(self):
        """Test lexing empty input."""
        lexer = Lexer("")
        tokens = lexer.tokenize()
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0].type, TokenType.EOF)
    
    def test_keywords(self):
        """Test all keywords."""
        keywords = {
            "func": TokenType.FUNC,
            "int": TokenType.INT,
            "void": TokenType.VOID,
            "if": TokenType.IF,
            "else": TokenType.ELSE,
            "for": TokenType.FOR,
            "return": TokenType.RETURN,
        }
        
        for keyword, expected_type in keywords.items():
            with self.subTest(keyword=keyword):
                lexer = Lexer(keyword)
                tokens = lexer.tokenize()
                self.assertEqual(len(tokens), 2)  # keyword + EOF
                self.assertEqual(tokens[0].type, expected_type)
                self.assertEqual(tokens[0].value, keyword)
    
    def test_identifiers(self):
        """Test identifier tokens."""
        test_cases = [
            "abc",
            "xyz123",
            "_underscore",
            "myVar",
            "variable_name",
            "a1b2c3",
        ]
        
        for identifier in test_cases:
            with self.subTest(identifier=identifier):
                lexer = Lexer(identifier)
                tokens = lexer.tokenize()
                self.assertEqual(len(tokens), 2)
                self.assertEqual(tokens[0].type, TokenType.IDENTIFIER)
                self.assertEqual(tokens[0].value, identifier)
    
    def test_integers(self):
        """Test integer literals."""
        test_cases = ["0", "1", "123", "999", "42"]
        
        for integer in test_cases:
            with self.subTest(integer=integer):
                lexer = Lexer(integer)
                tokens = lexer.tokenize()
                self.assertEqual(len(tokens), 2)
                self.assertEqual(tokens[0].type, TokenType.INTEGER)
                self.assertEqual(tokens[0].value, integer)
                self.assertEqual(int(tokens[0].value), int(integer))
    
    def test_single_char_operators(self):
        """Test single character operators."""
        operators = {
            "+": TokenType.PLUS,
            "-": TokenType.MINUS,
            "*": TokenType.MULTIPLY,
            "/": TokenType.DIVIDE,
            "%": TokenType.MODULO,
            "<": TokenType.LESS,
            ">": TokenType.GREATER,
            "!": TokenType.NOT,
            "=": TokenType.ASSIGN,
        }
        
        for op, expected_type in operators.items():
            with self.subTest(operator=op):
                lexer = Lexer(op)
                tokens = lexer.tokenize()
                self.assertEqual(len(tokens), 2)
                self.assertEqual(tokens[0].type, expected_type)
                self.assertEqual(tokens[0].value, op)
    
    def test_multi_char_operators(self):
        """Test multi-character operators."""
        operators = {
            "==": TokenType.EQUAL,
            "!=": TokenType.NOT_EQUAL,
            "<=": TokenType.LESS_EQUAL,
            ">=": TokenType.GREATER_EQUAL,
            "&&": TokenType.AND,
            "||": TokenType.OR,
            "->": TokenType.ARROW,
        }
        
        for op, expected_type in operators.items():
            with self.subTest(operator=op):
                lexer = Lexer(op)
                tokens = lexer.tokenize()
                self.assertEqual(len(tokens), 2)
                self.assertEqual(tokens[0].type, expected_type)
                self.assertEqual(tokens[0].value, op)
    
    def test_punctuation(self):
        """Test punctuation tokens."""
        punctuation = {
            "(": TokenType.LPAREN,
            ")": TokenType.RPAREN,
            "{": TokenType.LBRACE,
            "}": TokenType.RBRACE,
            ";": TokenType.SEMICOLON,
            ",": TokenType.COMMA,
        }
        
        for punct, expected_type in punctuation.items():
            with self.subTest(punctuation=punct):
                lexer = Lexer(punct)
                tokens = lexer.tokenize()
                self.assertEqual(len(tokens), 2)
                self.assertEqual(tokens[0].type, expected_type)
                self.assertEqual(tokens[0].value, punct)
    
    def test_whitespace_skipping(self):
        """Test that whitespace is properly skipped."""
        lexer = Lexer("   func   int   ")
        tokens = lexer.tokenize()
        # Should have FUNC, INT, EOF
        self.assertEqual(len(tokens), 3)
        self.assertEqual(tokens[0].type, TokenType.FUNC)
        self.assertEqual(tokens[1].type, TokenType.INT)
        self.assertEqual(tokens[2].type, TokenType.EOF)
    
    def test_comments(self):
        """Test single-line comments."""
        test_cases = [
            ("// comment", []),  # Only comment, no tokens
            ("func // comment", [TokenType.FUNC]),
            ("func main // comment", [TokenType.FUNC, TokenType.IDENTIFIER]),
            ("// comment\nfunc", [TokenType.FUNC]),  # Comment across line
            ("// comment\r\nfunc", [TokenType.FUNC]),  # Windows newline
        ]
        
        for source, expected_types in test_cases:
            with self.subTest(source=source):
                lexer = Lexer(source)
                tokens = lexer.tokenize()
                # Filter out EOF
                token_types = [t.type for t in tokens if t.type != TokenType.EOF]
                self.assertEqual(token_types, expected_types)
    
    def test_comment_line_tracking(self):
        """Ensure comments do not disrupt line/column tracking."""
        source = "func // comment\nmain"
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        
        self.assertEqual(tokens[0].type, TokenType.FUNC)
        # 'main' should be on the next line, column 1
        self.assertEqual(tokens[1].type, TokenType.IDENTIFIER)
        self.assertEqual(tokens[1].line, 2)
        self.assertEqual(tokens[1].column, 1)
    
    def test_line_column_tracking(self):
        """Test line and column tracking."""
        source = "func\nmain\n()"
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        
        # func at line 1, column 1
        self.assertEqual(tokens[0].type, TokenType.FUNC)
        self.assertEqual(tokens[0].line, 1)
        self.assertEqual(tokens[0].column, 1)
        
        # main at line 2, column 1
        self.assertEqual(tokens[1].type, TokenType.IDENTIFIER)
        self.assertEqual(tokens[1].line, 2)
        self.assertEqual(tokens[1].column, 1)
        
        # ( at line 3, column 1
        self.assertEqual(tokens[2].type, TokenType.LPAREN)
        self.assertEqual(tokens[2].line, 3)
        self.assertEqual(tokens[2].column, 1)
        
        # ) at line 3, column 2
        self.assertEqual(tokens[3].type, TokenType.RPAREN)
        self.assertEqual(tokens[3].line, 3)
        self.assertEqual(tokens[3].column, 2)
    
    def test_column_tracking_within_line(self):
        """Test column tracking within a single line."""
        source = "func main()"
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        
        # func at column 1
        self.assertEqual(tokens[0].column, 1)
        # main at column 6 (after "func ")
        self.assertEqual(tokens[1].column, 6)
        # ( at column 10 (after "func main")
        self.assertEqual(tokens[2].column, 10)
        # ) at column 11
        self.assertEqual(tokens[3].column, 11)
    
    def test_function_declaration(self):
        """Test lexing a function declaration."""
        source = "func main() -> void"
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        
        expected_types = [
            TokenType.FUNC,
            TokenType.IDENTIFIER,
            TokenType.LPAREN,
            TokenType.RPAREN,
            TokenType.ARROW,
            TokenType.VOID,
            TokenType.EOF,
        ]
        
        token_types = [t.type for t in tokens]
        self.assertEqual(token_types, expected_types)
        self.assertEqual(tokens[1].value, "main")
    
    def test_assignment(self):
        """Test lexing an assignment statement."""
        source = "a int = 1;"
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        
        expected_types = [
            TokenType.IDENTIFIER,
            TokenType.INT,
            TokenType.ASSIGN,
            TokenType.INTEGER,
            TokenType.SEMICOLON,
            TokenType.EOF,
        ]
        
        token_types = [t.type for t in tokens]
        self.assertEqual(token_types, expected_types)
        self.assertEqual(tokens[0].value, "a")
        self.assertEqual(tokens[3].value, "1")
    
    def test_expression_operators(self):
        """Test lexing expressions with various operators."""
        source = "a + b * c == d && e || f"
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        
        expected_types = [
            TokenType.IDENTIFIER,
            TokenType.PLUS,
            TokenType.IDENTIFIER,
            TokenType.MULTIPLY,
            TokenType.IDENTIFIER,
            TokenType.EQUAL,
            TokenType.IDENTIFIER,
            TokenType.AND,
            TokenType.IDENTIFIER,
            TokenType.OR,
            TokenType.IDENTIFIER,
            TokenType.EOF,
        ]
        
        token_types = [t.type for t in tokens]
        self.assertEqual(token_types, expected_types)
    
    def test_comparison_operators(self):
        """Test comparison operators."""
        source = "a < b <= c > d >= e != f == g"
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        
        expected_types = [
            TokenType.IDENTIFIER, TokenType.LESS,
            TokenType.IDENTIFIER, TokenType.LESS_EQUAL,
            TokenType.IDENTIFIER, TokenType.GREATER,
            TokenType.IDENTIFIER, TokenType.GREATER_EQUAL,
            TokenType.IDENTIFIER, TokenType.NOT_EQUAL,
            TokenType.IDENTIFIER, TokenType.EQUAL,
            TokenType.IDENTIFIER,
            TokenType.EOF,
        ]
        
        token_types = [t.type for t in tokens]
        self.assertEqual(token_types, expected_types)
    
    def test_unary_operators(self):
        """Test unary operators."""
        source = "-a !b"
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        
        expected_types = [
            TokenType.MINUS,
            TokenType.IDENTIFIER,
            TokenType.NOT,
            TokenType.IDENTIFIER,
            TokenType.EOF,
        ]
        
        token_types = [t.type for t in tokens]
        self.assertEqual(token_types, expected_types)
    
    def test_arrow_vs_minus(self):
        """Test that arrow operator is distinguished from minus."""
        # Arrow should be tokenized as ARROW, not MINUS
        lexer = Lexer("->")
        tokens = lexer.tokenize()
        self.assertEqual(tokens[0].type, TokenType.ARROW)
        self.assertEqual(tokens[0].value, "->")
        
        # Single minus should be MINUS
        lexer = Lexer("-")
        tokens = lexer.tokenize()
        self.assertEqual(tokens[0].type, TokenType.MINUS)
        self.assertEqual(tokens[0].value, "-")
        
        # Minus followed by something else should be MINUS
        lexer = Lexer("-a")
        tokens = lexer.tokenize()
        self.assertEqual(tokens[0].type, TokenType.MINUS)
        self.assertEqual(tokens[1].type, TokenType.IDENTIFIER)
    
    def test_assignment_vs_equality(self):
        """Test that assignment is distinguished from equality."""
        # Single = should be ASSIGN
        lexer = Lexer("=")
        tokens = lexer.tokenize()
        self.assertEqual(tokens[0].type, TokenType.ASSIGN)
        
        # == should be EQUAL
        lexer = Lexer("==")
        tokens = lexer.tokenize()
        self.assertEqual(tokens[0].type, TokenType.EQUAL)
        self.assertEqual(tokens[0].value, "==")
    
    def test_complex_expression(self):
        """Test lexing a complex expression."""
        source = "a + b * (c - d) / e"
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        
        expected_types = [
            TokenType.IDENTIFIER,
            TokenType.PLUS,
            TokenType.IDENTIFIER,
            TokenType.MULTIPLY,
            TokenType.LPAREN,
            TokenType.IDENTIFIER,
            TokenType.MINUS,
            TokenType.IDENTIFIER,
            TokenType.RPAREN,
            TokenType.DIVIDE,
            TokenType.IDENTIFIER,
            TokenType.EOF,
        ]
        
        token_types = [t.type for t in tokens]
        self.assertEqual(token_types, expected_types)
    
    def test_for_loop(self):
        """Test lexing a for loop."""
        source = "for (i int = 0; i < 10; i = i + 1) { }"
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        
        expected_types = [
            TokenType.FOR,
            TokenType.LPAREN,
            TokenType.IDENTIFIER,
            TokenType.INT,
            TokenType.ASSIGN,
            TokenType.INTEGER,
            TokenType.SEMICOLON,
            TokenType.IDENTIFIER,
            TokenType.LESS,
            TokenType.INTEGER,
            TokenType.SEMICOLON,
            TokenType.IDENTIFIER,
            TokenType.ASSIGN,
            TokenType.IDENTIFIER,
            TokenType.PLUS,
            TokenType.INTEGER,
            TokenType.RPAREN,
            TokenType.LBRACE,
            TokenType.RBRACE,
            TokenType.EOF,
        ]
        
        token_types = [t.type for t in tokens]
        self.assertEqual(token_types, expected_types)
    
    def test_if_statement(self):
        """Test lexing an if statement."""
        source = "if (a < b) { } else { }"
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        
        expected_types = [
            TokenType.IF,
            TokenType.LPAREN,
            TokenType.IDENTIFIER,
            TokenType.LESS,
            TokenType.IDENTIFIER,
            TokenType.RPAREN,
            TokenType.LBRACE,
            TokenType.RBRACE,
            TokenType.ELSE,
            TokenType.LBRACE,
            TokenType.RBRACE,
            TokenType.EOF,
        ]
        
        token_types = [t.type for t in tokens]
        self.assertEqual(token_types, expected_types)
    
    def test_function_call(self):
        """Test lexing a function call."""
        source = "foo(1, 2, 3)"
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        
        expected_types = [
            TokenType.IDENTIFIER,
            TokenType.LPAREN,
            TokenType.INTEGER,
            TokenType.COMMA,
            TokenType.INTEGER,
            TokenType.COMMA,
            TokenType.INTEGER,
            TokenType.RPAREN,
            TokenType.EOF,
        ]
        
        token_types = [t.type for t in tokens]
        self.assertEqual(token_types, expected_types)
        self.assertEqual(tokens[0].value, "foo")
        self.assertEqual(tokens[2].value, "1")
        self.assertEqual(tokens[4].value, "2")
        self.assertEqual(tokens[6].value, "3")
    
    def test_return_statement(self):
        """Test lexing a return statement."""
        source = "return 42;"
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        
        expected_types = [
            TokenType.RETURN,
            TokenType.INTEGER,
            TokenType.SEMICOLON,
            TokenType.EOF,
        ]
        
        token_types = [t.type for t in tokens]
        self.assertEqual(token_types, expected_types)
        self.assertEqual(tokens[1].value, "42")
    
    def test_identifier_vs_keyword(self):
        """Test that identifiers are distinguished from keywords."""
        # Keywords should be tokenized as keywords
        keywords = ["func", "int", "void", "if", "else", "for", "return"]
        for keyword in keywords:
            with self.subTest(keyword=keyword):
                lexer = Lexer(keyword)
                tokens = lexer.tokenize()
                self.assertNotEqual(tokens[0].type, TokenType.IDENTIFIER)
        
        # Similar looking identifiers should be tokenized as identifiers
        identifiers = ["func1", "intVar", "voidFunc", "ifelse", "returnValue"]
        for identifier in identifiers:
            with self.subTest(identifier=identifier):
                lexer = Lexer(identifier)
                tokens = lexer.tokenize()
                self.assertEqual(tokens[0].type, TokenType.IDENTIFIER)
    
    def test_error_token(self):
        """Test that unexpected characters produce error tokens."""
        source = "@#$"
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        
        # Should have error tokens for unexpected characters
        error_tokens = [t for t in tokens if t.type == TokenType.ERROR]
        self.assertGreater(len(error_tokens), 0)
    
    def test_mixed_content(self):
        """Test lexing mixed content with all token types."""
        source = """func add(x int, y int) -> int {
    return x + y;
}"""
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        
        # Filter out EOF
        token_types = [t.type for t in tokens if t.type != TokenType.EOF]
        
        # Should have all expected tokens
        self.assertIn(TokenType.FUNC, token_types)
        self.assertIn(TokenType.IDENTIFIER, token_types)
        self.assertIn(TokenType.LPAREN, token_types)
        self.assertIn(TokenType.INT, token_types)
        self.assertIn(TokenType.COMMA, token_types)
        self.assertIn(TokenType.ARROW, token_types)
        self.assertIn(TokenType.LBRACE, token_types)
        self.assertIn(TokenType.RETURN, token_types)
        self.assertIn(TokenType.PLUS, token_types)
        self.assertIn(TokenType.SEMICOLON, token_types)
        self.assertIn(TokenType.RBRACE, token_types)
    
    def test_consecutive_numbers(self):
        """Test that consecutive numbers are tokenized separately."""
        source = "1 2 3"
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        
        integers = [t for t in tokens if t.type == TokenType.INTEGER]
        self.assertEqual(len(integers), 3)
        self.assertEqual(integers[0].value, "1")
        self.assertEqual(integers[1].value, "2")
        self.assertEqual(integers[2].value, "3")
    
    def test_identifier_with_numbers(self):
        """Test identifiers that contain numbers."""
        source = "var1 var2 abc123"
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        
        identifiers = [t for t in tokens if t.type == TokenType.IDENTIFIER]
        self.assertEqual(len(identifiers), 3)
        self.assertEqual(identifiers[0].value, "var1")
        self.assertEqual(identifiers[1].value, "var2")
        self.assertEqual(identifiers[2].value, "abc123")


if __name__ == "__main__":
    unittest.main()

