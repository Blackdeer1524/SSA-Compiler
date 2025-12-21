import textwrap
from src.optimizations.licm import LICM
from src.optimizations.sccp import SCCP
from tests import base


class TestSCCPandLICM(base.TestBase):
    def __init__(self, *args):
        passes = [SCCP, LICM]
        super().__init__(passes, *args)

    def test_for_loop_with_trivial_cond(self):
        src = """
            func main() -> int {
                let x int = 0;
                let a int = 1;
                let b int = 2;
                for (let i int = 0; 1; i = i + 1) {
                    for (let j int = 0; 0; j = j + 1) {
                        // the loop just adds some empty blocks 
                    }

                    if (foo()) {
                        x = 2;  // invariant
                        if (bar()) {
                            a = 3; // not invariant
                            break;
                        } else {
                            b = 4; // not invariant
                            break;
                        }

                    }
                }
                return x;
            }

            func bar() -> int {
                return 2;
            }

            func foo() -> int {
                return 1;
            }
        """

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                x_v1 = 0
                a_v1 = 1
                b_v1 = 2
                jmp BB2
            ; succ: [BB2]

            ; pred: [BB0]
            BB2: ; [condition check]
                i_v1 = 0
                jmp BB3
            ; succ: [BB3]

            ; pred: [BB2]
            BB3: ; [loop preheader]
                j_v1 = 0
                x_v3 = 2
                jmp BB4
            ; succ: [BB4]

            ; pred: [BB3, BB5]
            BB4: ; [loop body]
                x_v2 = ϕ(BB3: 0, BB5: 0)
                i_v2 = ϕ(BB3: 0, BB5: i_v3)

                jmp BB8
            ; succ: [BB8]

            ; pred: [BB4]
            BB8: ; [condition check]
                jmp BB13
            ; succ: [BB13]

            ; pred: [BB8]
            BB13: ; [loop exit]
                %5_v1 = foo()
                cmp(%5_v1, 0)
                if CF == 0 then jmp BB14 else jmp BB15
            ; succ: [BB14, BB15]

            ; pred: [BB13]
            BB15: ; [merge]
                x_v4 = ϕ(BB13: 0)

                jmp BB5
            ; succ: [BB5]

            ; pred: [BB15]
            BB5: ; [loop latch]
                i_v3 = i_v2 + 1
                jmp BB4
            ; succ: [BB4]

            ; pred: [BB13]
            BB14: ; [then]
                %6_v1 = bar()
                cmp(%6_v1, 0)
                if CF == 0 then jmp BB16 else jmp BB18
            ; succ: [BB16, BB18]

            ; pred: [BB14]
            BB18: ; [else]
                b_v2 = 4
                jmp BB6
            ; succ: [BB6]

            ; pred: [BB18, BB16]
            BB6: ; [loop tail]
                x_v5 = ϕ(BB16: 2, BB18: 2)

                jmp BB7
            ; succ: [BB7]

            ; pred: [BB6]
            BB7: ; [loop exit]
                x_v6 = ϕ(BB6: 2)

                return(2)
            ; succ: [BB1]

            ; pred: [BB7]
            BB1: ; [exit]
            ; succ: []

            ; pred: [BB14]
            BB16: ; [then]
                a_v2 = 3
                jmp BB6
            ; succ: [BB6]
        """).strip()

        self.assert_ir(src, expected_ir)

    def test_tail_dominance_dominance_with_redefinition(self):
        src = """
            func main() -> int {
                let v int = 0;
                for (let i int = 0; 1; i = i + 1) {
                    if (foo()) {
                        v = 2; // hoist
                        break;
                    }
                    v = 3;
                }
                return v;
            }
            
            func foo() -> int {
                return 42;
            }
        """

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                v_v1 = 0
                jmp BB2
            ; succ: [BB2]

            ; pred: [BB0]
            BB2: ; [condition check]
                i_v1 = 0
                jmp BB3
            ; succ: [BB3]

            ; pred: [BB2]
            BB3: ; [loop preheader]
                v_v3 = 2
                jmp BB4
            ; succ: [BB4]

            ; pred: [BB3, BB5]
            BB4: ; [loop body]
                i_v2 = ϕ(BB3: 0, BB5: i_v3)

                %1_v1 = foo()
                cmp(%1_v1, 0)
                if CF == 0 then jmp BB8 else jmp BB9
            ; succ: [BB8, BB9]

            ; pred: [BB4]
            BB9: ; [merge]
                v_v4 = 3
                jmp BB5
            ; succ: [BB5]

            ; pred: [BB9]
            BB5: ; [loop latch]
                i_v3 = i_v2 + 1
                jmp BB4
            ; succ: [BB4]

            ; pred: [BB4]
            BB8: ; [then]
                jmp BB6
            ; succ: [BB6]

            ; pred: [BB8]
            BB6: ; [loop tail]
                v_v2 = ϕ(BB8: 2)

                jmp BB7
            ; succ: [BB7]

            ; pred: [BB6]
            BB7: ; [loop exit]
                v_v5 = ϕ(BB6: 2)

                return(2)
            ; succ: [BB1]

            ; pred: [BB7]
            BB1: ; [exit]
            ; succ: []
        """).strip()

        self.assert_ir(src, expected_ir)
