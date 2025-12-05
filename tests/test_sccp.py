import re
import textwrap
import unittest

from src.optimizations.sccp import SCCP
from src.parsing.lexer import Lexer
from src.parsing.parser import Parser
from src.parsing.semantic import SemanticAnalyzer
from src.ssa.cfg import CFG, CFGBuilder
from src.ssa.dominance import compute_dominance_frontier_graph, compute_dominator_tree
from src.ssa.ir_visualizer import ir_to_graphviz
from src.ssa.ssa import SSABuilder


class TestSCCP(unittest.TestCase):
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
        ir = main.to_IR().strip()
        
        if expected_ir == ir:
            return

        expected_graph = ir_to_graphviz(expected_ir)
        actual_graph = ir_to_graphviz(ir)
        actual_graph = re.sub(r"(BB\d+)", r"'\1",actual_graph)
        
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

    def test_constant_prop(self):
        src = self.make_main("""
        a int = 0;
        return a;
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                a_v1 = 0
                return(0)
            ; succ: []        
        """).strip()

        self.assert_ir(src, expected_ir)
    
    def test_transition_const(self):
        src = self.make_main("""
            a int = 0;
            b int = a + 10;
            return b;
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                a_v1 = 0
                b_v1 = 10
                return(10)
            ; succ: []
        """).strip()

        self.assert_ir(src, expected_ir)
    
    def test_simple_unreachable_block_drop(self):
        src = self.make_main("""
            a int = 0;
            if (a > 0) {
                a = 10;
            }
            return a;
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                a_v1 = 0
                %0_v1 = 0
                jmp BB3
            ; succ: [BB3]

            ; pred: [BB0]
            BB3: ; [merge]
                a_v2 = ϕ(BB0: 0)

                return(0)
            ; succ: []
        """).strip()

        self.assert_ir(src, expected_ir)
      
    def test_interblock_propogation(self):
        src = self.make_main("""
            a int = 5;
            b int = 10;
            if (a == 5) {
                b = a + 10;  // b = 15
            }
            return b;  // return 15
        """)
        
        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                a_v1 = 5
                b_v1 = 10
                %0_v1 = 1
                jmp BB2
            ; succ: [BB2]

            ; pred: [BB0]
            BB2: ; [then]
                b_v3 = 15
                jmp BB3
            ; succ: [BB3]

            ; pred: [BB2]
            BB3: ; [merge]
                b_v2 = ϕ(BB0: 10, BB2: 15)

                return(15)
            ; succ: []
          """).strip()

        self.assert_ir(src, expected_ir)

    def test_dead_cycle(self):
        src = self.make_main("""
            N int = 0;
            for (i int = 0; i < N; i = i + 1) { 
                N = (N + 1) * 2;
            }
            return N; // 0 
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                N_v1 = 0
                jmp BB2
            ; succ: [BB2]

            ; pred: [BB0]
            BB2: ; [loop init]
                i_v1 = 0
                jmp BB3
            ; succ: [BB3]

            ; pred: [BB2]
            BB3: ; [loop header]
                N_v2 = ϕ(BB2: 0)
                i_v2 = ϕ(BB2: 0)

                %0_v1 = 0
                jmp BB4
            ; succ: [BB4]

            ; pred: [BB3]
            BB4: ; [loop exit]
                return(0)
            ; succ: []
        """).strip()

        self.assert_ir(src, expected_ir)
    
    def test_initially_dead_condition(self):
        src = self.make_main("""
            N int = 0;
            for (i int = 0; i < 10; i = i + 1) {
                if (N > 10) { // is initially considered as unreachable
                    break;  
                }
                N = (N + 1) * 2;
            }
            return N;
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                N_v1 = 0
                jmp BB2
            ; succ: [BB2]

            ; pred: [BB0]
            BB2: ; [loop init]
                i_v1 = 0
                jmp BB3
            ; succ: [BB3]

            ; pred: [BB2, BB6]
            BB3: ; [loop header]
                N_v2 = ϕ(BB2: 0, BB6: N_v3)
                i_v2 = ϕ(BB2: 0, BB6: i_v3)

                %0_v1 = i_v2 < 10
                cmp(%0_v1, 1)
                if CF == 1 then jmp BB5 else jmp BB4
            ; succ: [BB5, BB4]

            ; pred: [BB3, BB7]
            BB4: ; [loop exit]
                return(N_v2)
            ; succ: []

            ; pred: [BB3]
            BB5: ; [loop body]
                %3_v1 = N_v2 > 10
                cmp(%3_v1, 1)
                if CF == 1 then jmp BB7 else jmp BB8
            ; succ: [BB8, BB7]

            ; pred: [BB5]
            BB7: ; [then]
                jmp BB4
            ; succ: [BB4]

            ; pred: [BB5]
            BB8: ; [merge]
                %6_v1 = N_v2 + 1
                N_v3 = %6_v1 * 2
                jmp BB6
            ; succ: [BB6]

            ; pred: [BB8]
            BB6: ; [loop update]
                i_v3 = i_v2 + 1
                jmp BB3
            ; succ: [BB3]
        """).strip()

        self.assert_ir(src, expected_ir)
          
    def test_break_on_first_iter(self):
        src = self.make_main("""
            N int = 5;
            for (i int = 0; i < 10; i = i + 1) {
                if (N < 10) { 
                    break;
                }
                N = (N + 1) * 2;
            }
            return N;
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                N_v1 = 5
                jmp BB2
            ; succ: [BB2]
            
            ; pred: [BB0]
            BB2: ; [loop init]
                i_v1 = 0
                jmp BB3
            ; succ: [BB3]
            
            ; pred: [BB2]
            BB3: ; [loop header]
                N_v2 = ϕ(BB2: 5)
                i_v2 = ϕ(BB2: 0)
            
                %0_v1 = 1
                jmp BB5
            ; succ: [BB5]
            
            ; pred: [BB3]
            BB5: ; [loop body]
                %3_v1 = 1
                jmp BB7
            ; succ: [BB7]
            
            ; pred: [BB5]
            BB7: ; [then]
                jmp BB4
            ; succ: [BB4]
            
            ; pred: [BB7]
            BB4: ; [loop exit]
                return(5)
            ; succ: []
        """).strip()
        self.assert_ir(src, expected_ir)

    def test_break_on_first_iter_transitional(self):
        src = self.make_main("""
          N int = 5;
          a int = 0;
          for (i int = 0; i < 10; i = i + 1) {
              if (a != 0) {
                  N = N + 1;
                  break;
              }
          }
          return N;  // 5
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                N_v1 = 5
                a_v1 = 0
                jmp BB2
            ; succ: [BB2]

            ; pred: [BB0]
            BB2: ; [loop init]
                i_v1 = 0
                jmp BB3
            ; succ: [BB3]

            ; pred: [BB2, BB6]
            BB3: ; [loop header]
                i_v2 = ϕ(BB2: 0, BB6: i_v3)

                %0_v1 = i_v2 < 10
                cmp(%0_v1, 1)
                if CF == 1 then jmp BB5 else jmp BB4
            ; succ: [BB5, BB4]

            ; pred: [BB3]
            BB4: ; [loop exit]
                N_v2 = ϕ(BB3: 5)

                return(5)
            ; succ: []

            ; pred: [BB3]
            BB5: ; [loop body]
                %3_v1 = 0
                jmp BB8
            ; succ: [BB8]

            ; pred: [BB5]
            BB8: ; [merge]
                jmp BB6
            ; succ: [BB6]

            ; pred: [BB8]
            BB6: ; [loop update]
                i_v3 = i_v2 + 1
                jmp BB3
            ; succ: [BB3]
        """).strip()

        self.assert_ir(src, expected_ir)

