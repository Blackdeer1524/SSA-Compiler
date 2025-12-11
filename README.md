# SSA-based compiler

Небольшой оптимизирующий компилятор с промежуточным представллением в SSA форм.

Пайплайн: лексер → парсер (AST) → семантический анализ → построение CFG → проставление SSA → оптимизации → вывод IR или CFG в Graphviz.

- Оптимизации:

  - `LICM` (вынос инвариантов из циклов),
  - `SCCP` (разреженная константная пропагация + отсечение недостижимых путей/блоков),
  - `DCE` (удаление мёртвых инструкций с учётом стор/аргументов).

  Можно отключать отдельными флагами.

- Ввод/вывод: исходник читается из `--input` (по умолчанию `input.txt`). Вывод по умолчанию — CFG в Graphviz на stdout; `--dump-cfg-dot PATH` сохраняет `.dot`, `--dump-ir PATH` — текстовый SSA IR.
- Управление флагами: `--disable-ssa`, `--disable-licm`, `--disable-sccp`, `--disable-dce`, `--disable-idom-tree`, `--disable-df`. Все флаги оставьте включёнными для полного оптимизирующего конвейера.
- Тесты: `pytest tests` (см. наборы для лексера/парсера/семантики/SSA/оптимизаций).

## Пример кода

```
// Поддерживаются int и массивы фикс. размера
func foo(arg int, foo [64]int) -> int { return arg + foo[2]; }

func main() -> void {
    let a int = 1;
    let b int = 2 + (-a);
    let arr [64]int = {};
    let matrix [128][64]int = {};
    let x int = arr[0];
    let y int = matrix[10][20];
    arr[0] = 42;
    matrix[i][j] = 100;

    for { /* unconditional */ }
    for (let i int = 0; i < 10; i = i + 1) { }

    if (i <= 10 || i > 40 && i + 2 < i - 1) { ... } else { ... }

    foo(1, arr);
    let flag int = 1 < 20;
}
```

## Грамматика

```
PROGRAMM ::= FUNCTION+

FUNCTION ::= func %name% "(" ARG_LIST ")" "->" TYPE "{" BLOCK "}"

ARG_LIST ::= EPSILON | ARG ("," ARG)*

ARG ::= %name% TYPE

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

ASSIGNMENT ::= "let" %name% TYPE "=" (EXPR | "{}") ";"

REASSIGNMENT ::= EXPR_LVALUE "=" EXPR ";"

EXPR_LVALUE ::= %name% ("[" EXPR "]")*

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
    %name% ("[" EXPR "]")*
    | %integer%
    | "(" EXPR ")"
    | FUNCTION_CALL
```
