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


class TestDCE(unittest.TestCase):
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
        DCE().run(main)
        ir = main.to_IR().strip()
        
        if expected_ir == ir:
            return

        ir = ir.replace("<", "&lt;").replace(">", "&gt;")
        expected_ir = expected_ir.replace("<", "&lt;").replace(">", "&gt;")
        
        expected_graph = ir_to_graphviz(expected_ir)
        actual_graph = ir_to_graphviz(ir)
        actual_graph = re.sub(r"(BB\d+)", r"\1",actual_graph)
        
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
    
    def test_simple(self):
        src = self.make_main("""
        a int = 0;
        return a;
        """)
        
        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                a_v1 = 0
                return(a_v1)
            ; succ: [BB1]

            ; pred: [BB0]
            BB1: ; [exit]
            ; succ: []
        """).strip()

        self.assert_ir(src, expected_ir)
        
    def test_complex_elim(self):
        src = self.make_main("""
        a int = 0;
        for (i int = 0; i < 10; i = i + 1) {
            a = a * 2;
        }
        return 1;
        """)
        
        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                jmp BB2
            ; succ: [BB2]

            ; pred: [BB0]
            BB2: ; [loop init]
                i_v1 = 0
                jmp BB3
            ; succ: [BB3]

            ; pred: [BB2, BB6]
            BB3: ; [loop header]
                i_v2 = ϕ(BB2: i_v1, BB6: i_v3)

                %0_v1 = i_v2 &lt; 10
                cmp(%0_v1, 1)
                if CF == 1 then jmp BB5 else jmp BB4
            ; succ: [BB5, BB4]

            ; pred: [BB3]
            BB4: ; [loop exit]
                return(1)
            ; succ: [BB1]

            ; pred: [BB4]
            BB1: ; [exit]
            ; succ: []

            ; pred: [BB3]
            BB5: ; [loop body]
                jmp BB6
            ; succ: [BB6]

            ; pred: [BB5]
            BB6: ; [loop update]
                i_v3 = i_v2 + 1
                jmp BB3
            ; succ: [BB3]
        """).strip()

        self.assert_ir(src, expected_ir)
    
    def test_dead_reassign(self):
        src = self.make_main("""
            a int = 1;
            if (a == 1) { 
                a = 3;
            }
            
            a = 12;  // unused var -> dead code
            return 1;
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                a_v1 = 1
                %0_v1 = a_v1 == 1
                cmp(%0_v1, 1)
                if CF == 1 then jmp BB2 else jmp BB3
            ; succ: [BB3, BB2]

            ; pred: [BB0]
            BB2: ; [then]
                jmp BB3
            ; succ: [BB3]

            ; pred: [BB0, BB2]
            BB3: ; [merge]
                return(1)
            ; succ: [BB1]

            ; pred: [BB3]
            BB1: ; [exit]
            ; succ: []

            ; pred: [BB0, BB2]
            BB3: ; [merge]
                return(1)
            ; succ: [BB1]
        """).strip()

        self.assert_ir(src, expected_ir)
           
        