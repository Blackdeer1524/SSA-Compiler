import re
import textwrap
import unittest

from src.parsing.lexer import Lexer
from src.parsing.parser import Parser
from src.parsing.semantic import SemanticAnalyzer
from src.ssa.cfg import CFG, CFGBuilder
from src.ssa.ir_visualizer import ir_to_graphviz
from src.ssa.ssa import SSABuilder


class TestBase(unittest.TestCase):
    def __init__(self, passes: list = [], *args):
        self.passes = passes
        super().__init__(*args)

    def setUp(self) -> None:
        self.maxDiff = None
        # Call super().setUp() if needed.
        super().setUp()
        # Optionally, initialize variables in param_vars as attributes
        for k, v in getattr(self, "param_vars", {}).items():
            setattr(self, k, v)

    def parse_programm(self, src: str) -> CFG:
        lexer = Lexer(src)
        parser = Parser(lexer)
        ast = parser.parse()
        analyzer = SemanticAnalyzer(ast)

        errors = analyzer.analyze()
        self.assertListEqual(errors, [])

        builder = CFGBuilder()
        cfgs = builder.build(ast)
        self.assertEqual(cfgs[0].name, "main")

        ssa_builder = SSABuilder()
        ssa_builder.build(cfgs[0])

        return cfgs[0]

    def make_main(self, prog) -> str:
        return f"func main() -> int {{  {prog}  }}"

    def assert_ir(self, src: str, expected_ir: str):
        main = self.parse_programm(src)

        for p in self.passes:
            p().run(main)

        ir = main.to_IR().strip()
        if expected_ir == ir:
            return

        no_opts_ir = (
            self.parse_programm(src)
            .to_IR()
            .strip()
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        expected_graph = ir_to_graphviz(expected_ir.replace("<", "&lt;").replace(">", "&gt;"))
        actual_graph = ir_to_graphviz(ir.replace("<", "&lt;").replace(">", "&gt;"))
        actual_graph = re.sub(r"(BB\d+)", r"\1'", actual_graph)
        no_opts_graph = ir_to_graphviz(no_opts_ir)
        no_opts_graph = re.sub(r"(BB\d+)", r"\1^", no_opts_graph)

        block_src_code = (
            textwrap.dedent(src)
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", '<br ALIGN="left"/>')
            + '<br ALIGN="left"/>'
        )
        source_block = f'"src" [label=<{block_src_code}>]'

        message = textwrap.dedent(f"""
        digraph G {{
            subgraph cluster_source_code {{
                node [shape=box]
                label="Source";
                color=blue;
            {source_block}
            }}
        
            subgraph cluster_expected {{
                label="Expected";
                color=green;
            {expected_graph}
            }}

            subgraph cluster_actual {{
                label="Actual";
                color=red;
            {actual_graph}
            }}
                                  
            subgraph cluster_original {{
                label="Original";
                color=blue;
            {no_opts_graph}
            }}
        }}
        """)

        self.assertEqual(expected_ir, ir, message)
