import re
import textwrap
import unittest

from src.parsing.lexer import Lexer
from src.parsing.parser import Parser
from src.parsing.semantic import SemanticAnalyzer
from src.ssa.cfg import CFG, CFGBuilder
from src.ssa.ir_visualizer import ir_to_graphviz
from src.ssa.ssa import SSABuilder
from src.optimizations.dce import DCE
from src.optimizations.sccp import SCCP


class TestSCCPAndDCE(unittest.TestCase):
    def setUp(self) -> None:
        self.maxDiff = None
        return super().setUp()

    def parse_programm(self, src: str) -> CFG:
        lexer = Lexer(src)
        parser = Parser(lexer)
        ast = parser.parse()
        analyzer = SemanticAnalyzer(ast)

        errors = analyzer.analyze()
        self.assertListEqual(errors, [])
        
        builder = CFGBuilder()
        cfgs = builder.build(ast)
        self.assertEqual(len(cfgs), 1)
        
        ssa_builder = SSABuilder()
        ssa_builder.build(cfgs[0])
        
        return cfgs[0]

    def make_main(self, prog) -> str:
        return f"func main() -> int {{  {prog}  }}"

    def assert_ir(self, src: str, expected_ir: str):
        main = self.parse_programm(src)
        SCCP().run(main)
        DCE().run(main)
        ir = main.to_IR().strip()
        
        if expected_ir == ir:
            return

        ir = ir.replace("<", "&lt;").replace(">", "&gt;")
        expected_ir = expected_ir.replace("<", "&lt;").replace(">", "&gt;")
        
        expected_graph = ir_to_graphviz(expected_ir)
        actual_graph = ir_to_graphviz(ir)
        actual_graph = re.sub(r"(BB\d+)", r"\1'",actual_graph)
        
        message = textwrap.dedent(f"""
        digraph G {{
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
        }}
        """)
        
        self.assertEqual(expected_ir, ir, message)

    def test_dead_on_condition(self):
        src = self.make_main("""
            a int = 0; // dead
            N int = 0;
            if (N == 0) {
                return N;
            }
            // dead code
            a = N + 10;
            return a;
        """)
        
        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                jmp BB2
            ; succ: [BB2]

            ; pred: [BB0]
            BB2: ; [then]
                return(0)
            ; succ: []
        """).strip()
        
        self.assert_ir(src, expected_ir)
    
    def test_dead_loop_causes_dead_code(self):
        src = self.make_main("""
            N int = 0;
            a int = 0;
            c int = 0;
            for (i int = 0; i < N; i = i + 1) {
                a = (a + 1) * 2;
            }
            return c;
        """)
        
        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                jmp BB2
            ; succ: [BB2]

            ; pred: [BB0]
            BB2: ; [loop init]
                jmp BB3
            ; succ: [BB3]

            ; pred: [BB2]
            BB3: ; [loop header]
                jmp BB4
            ; succ: [BB4]

            ; pred: [BB3]
            BB4: ; [loop exit]
                return(0)
            ; succ: []
        """).strip()

        self.assert_ir(src, expected_ir)