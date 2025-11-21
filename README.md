```
// пока что поддерживается только int

// всё передается на стеке
func foo(arg int, foo int) -> int {
    ...
    return 1 + 2;
} 

func main() -> void {
    a int = 1;
    b int = 2 + (-a);
    
    // unconditional loop
    for {
        ...
    }
    
    i int = 0;
    if (i < 10) {
        a int = 20; // forbidden!!!
    }
    
    // `for` loop
    for (i int = 0; i < 10; i = i + 1) {
    }
    
    // function calling
    foo(1, 2);
    
    a int = 1 < 20;

    // branching
    if (i <= 10 || i > 40 && i + 2 < i - 1) {
        ...
    } else { // optional else branch
        ...
    }
    
    // break and continue
    for (i int = 0; i < 10; i = i + 1) {
        if (i == 5) {
            break;
        }
        if (i == 3) {
            continue;
        }
    }
}
```

## Grammar

```
PROGRAMM ::= FUNCTION+

FUNCTION ::= func %name% "(" ARG_LIST ")" "->" TYPE "{" BLOCK "}"

ARG_LIST ::= EPSILON | ARG ("," ARG)*

ARG ::= %name% %type%

TYPE ::= int | void

BLOCK ::= "{" STATEMENTS "}"

STATEMENTS ::= STATEMENT*

STATEMENT ::= 
    ASSIGNMENT 
    | REASSIGNMENT
    | CONDITION
    | LOOP
    | FUNCTION_CALL ";"
    | RETURN ";"
    | BREAK ";"
    | CONTINUE ";"
    | BLOCK

ASSIGNMENT ::= %name% %type% "=" EXPR ";"

REASSIGNMENT ::= %name% "=" EXPR ";"

CONDITION ::= if "(" EXPR ")" BLOCK [else BLOCK]

LOOP ::= 
    for BLOCK
    | for "(" ASSIGNMENT ";" EXPR ";" REASSIGNMENT ")" BLOCK

FUNCTION_CALL ::= %name% "(" EXPR_LIST ")"

EXPR_LIST ::= EPSILON | EXPR ("," EXPR)*

RETURN ::= return [EXPR]

BREAK ::= break

CONTINUE ::= continue

EXPR ::= EXPR_OR

EXPR_OR ::= EXPR_AND ("||" EXPR_AND)*

EXPR_AND ::= EXPR_COMP ("&&" EXPR_COMP)*

EXPR_COMP ::= EXPR_ADD (("==" | "!=" | "<" | "<=" | ">" | ">=") EXPR_ADD)*

EXPR_ADD ::= EXPR_MUL (("+" | "-") EXPR_MUL)*

EXPR_MUL ::= EXPR_UNARY (("*" | "/" | "%") EXPR_UNARY)*

EXPR_UNARY ::= 
    EXPR_ATOM
    | "-" EXPR_UNARY
    | "!" EXPR_UNARY

EXPR_ATOM ::= 
    %name%
    | %integer%
    | "(" EXPR ")"
    | FUNCTION_CALL
```