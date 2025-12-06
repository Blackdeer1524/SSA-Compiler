import textwrap
from src.optimizations.licm import LICM
from tests import base


class TestLICM(base.TestBase):
    def __init__(self, *args):
        passes = [LICM]
        super().__init__(passes, *args)

    def test_simple(self):
        src = self.make_main("""
            a int = 0;
            for (i int = 0; i < 10; i = i + 1) {
                a = 10;
            }
            return a;
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                a_v1 = 0
                jmp BB2
            ; succ: [BB2]

            ; pred: [BB0]
            BB2: ; [condition check]
                i_v1 = 0
                %0_v1 = i_v1 &lt; 10
                cmp(%0_v1, 1)
                if CF == 1 then jmp BB3 else jmp BB7
            ; succ: [BB3, BB7]

            ; pred: [BB2, BB6]
            BB7: ; [loop exit]
                a_v3 = ϕ(BB2: a_v1, BB6: a_v2)

                return(a_v3)
            ; succ: [BB1]

            ; pred: [BB7]
            BB1: ; [exit]
            ; succ: []

            ; pred: [BB2]
            BB3: ; [loop preheader]
                a_v2 = 10
                jmp BB4
            ; succ: [BB4]

            ; pred: [BB3, BB5]
            BB4: ; [loop header]
                i_v2 = ϕ(BB3: i_v1, BB5: i_v3)

                jmp BB5
            ; succ: [BB5]

            ; pred: [BB4]
            BB5: ; [loop update]
                i_v3 = i_v2 + 1
                %5_v1 = i_v3 &lt; 10
                cmp(%5_v1, 1)
                if CF == 1 then jmp BB4 else jmp BB7
            ; succ: [BB4, BB6]

            ; pred: [BB5]
            BB6: ; [loop tail]
                jmp BB7
            ; succ: [BB7]       
        """).strip()
        self.assert_ir(src, expected_ir)

    def test_nested_loops(self):
        src = self.make_main("""
            a int = 0;
            for (i int = 0; i < 10; i = i + 1) {
                for (j int = 0; j < 10; j = j + 1) {
                }
            }
            return a;
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                a_v1 = 0
                jmp BB2
            ; succ: [BB2]

            ; pred: [BB0]
            BB2: ; [condition check]
                i_v1 = 0
                %0_v1 = i_v1 &lt; 10
                cmp(%0_v1, 1)
                if CF == 1 then jmp BB3 else jmp BB7
            ; succ: [BB3, BB7]

            ; pred: [BB2, BB6]
            BB7: ; [loop exit]
                return(a_v1)
            ; succ: [BB1]

            ; pred: [BB7]
            BB1: ; [exit]
            ; succ: []

            ; pred: [BB2]
            BB3: ; [loop preheader]
                j_v1 = 0
                %3_v1 = j_v1 &lt; 10
                jmp BB4
            ; succ: [BB4]

            ; pred: [BB3, BB5]
            BB4: ; [loop header]
                i_v2 = ϕ(BB3: i_v1, BB5: i_v3)

                jmp BB8
            ; succ: [BB8]

            ; pred: [BB4]
            BB8: ; [condition check]
                cmp(%3_v1, 1)
                if CF == 1 then jmp BB9 else jmp BB13
            ; succ: [BB9, BB13]

            ; pred: [BB8, BB12]
            BB13: ; [loop exit]
                jmp BB5
            ; succ: [BB5]

            ; pred: [BB13]
            BB5: ; [loop update]
                i_v3 = i_v2 + 1
                %13_v1 = i_v3 &lt; 10
                cmp(%13_v1, 1)
                if CF == 1 then jmp BB4 else jmp BB7
            ; succ: [BB4, BB6]

            ; pred: [BB5]
            BB6: ; [loop tail]
                jmp BB7
            ; succ: [BB7]

            ; pred: [BB8]
            BB9: ; [loop preheader]
                jmp BB10
            ; succ: [BB10]

            ; pred: [BB9, BB11]
            BB10: ; [loop header]
                j_v2 = ϕ(BB9: j_v1, BB11: j_v3)

                jmp BB11
            ; succ: [BB11]

            ; pred: [BB10]
            BB11: ; [loop update]
                j_v3 = j_v2 + 1
                %8_v1 = j_v3 &lt; 10
                cmp(%8_v1, 1)
                if CF == 1 then jmp BB10 else jmp BB13
            ; succ: [BB10, BB12]

            ; pred: [BB11]
            BB12: ; [loop tail]
                jmp BB13
            ; succ: [BB13]
        """).strip()
        self.assert_ir(src, expected_ir)

    def test_dead_loop_hoisting(self):
        src = """
            func main() -> int {
                N int = foo(); 
                x int = 0;
                for (i int = 0; i < N; i = i + 1) {
                    x = 11; 
                }
                return x;
            }

            func foo() -> int {
                return -42;
            }        
        """

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                N_v1 = foo()
                x_v1 = 0
                jmp BB2
            ; succ: [BB2]

            ; pred: [BB0]
            BB2: ; [condition check]
                i_v1 = 0
                %0_v1 = i_v1 &lt; N_v1
                cmp(%0_v1, 1)
                if CF == 1 then jmp BB3 else jmp BB7
            ; succ: [BB3, BB7]

            ; pred: [BB2, BB6]
            BB7: ; [loop exit]
                x_v2 = ϕ(BB2: x_v1, BB6: x_v3)

                return(x_v2)
            ; succ: [BB1]

            ; pred: [BB7]
            BB1: ; [exit]
            ; succ: []

            ; pred: [BB2]
            BB3: ; [loop preheader]
                x_v3 = 11
                jmp BB4
            ; succ: [BB4]

            ; pred: [BB3, BB5]
            BB4: ; [loop header]
                i_v2 = ϕ(BB3: i_v1, BB5: i_v3)

                jmp BB5
            ; succ: [BB5]

            ; pred: [BB4]
            BB5: ; [loop update]
                i_v3 = i_v2 + 1
                %5_v1 = i_v3 &lt; N_v1
                cmp(%5_v1, 1)
                if CF == 1 then jmp BB4 else jmp BB7
            ; succ: [BB4, BB6]

            ; pred: [BB5]
            BB6: ; [loop tail]
                jmp BB7
            ; succ: [BB7]       
        """).strip()
        self.assert_ir(src, expected_ir)

    def test_conditional_reassignment(self):
        src = """
            func main() -> int {
                v int = 0;
                for (i int = 0; i < 10; i = i + 1) {
                    N int = foo();
                    if (N == 0) {
                        v = 2;
                    }
                }
                return v;
            }

            func foo() -> int {
                return -42;
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
                %0_v1 = i_v1 &lt; 10
                cmp(%0_v1, 1)
                if CF == 1 then jmp BB3 else jmp BB7
            ; succ: [BB3, BB7]

            ; pred: [BB2, BB6]
            BB7: ; [loop exit]
                v_v5 = ϕ(BB2: v_v1, BB6: v_v4)

                return(v_v5)
            ; succ: [BB1]

            ; pred: [BB7]
            BB1: ; [exit]
            ; succ: []

            ; pred: [BB2]
            BB3: ; [loop preheader]
                jmp BB4
            ; succ: [BB4]

            ; pred: [BB3, BB5]
            BB4: ; [loop header]
                v_v2 = ϕ(BB3: v_v1, BB5: v_v4)
                i_v2 = ϕ(BB3: i_v1, BB5: i_v3)

                N_v1 = foo()
                %3_v1 = N_v1 == 0
                cmp(%3_v1, 1)
                if CF == 1 then jmp BB8 else jmp BB9
            ; succ: [BB9, BB8]

            ; pred: [BB4]
            BB8: ; [then]
                v_v3 = 2
                jmp BB9
            ; succ: [BB9]

            ; pred: [BB4, BB8]
            BB9: ; [merge]
                v_v4 = ϕ(BB4: v_v2, BB8: v_v3)

                jmp BB5
            ; succ: [BB5]

            ; pred: [BB9]
            BB5: ; [loop update]
                i_v3 = i_v2 + 1
                %8_v1 = i_v3 &lt; 10
                cmp(%8_v1, 1)
                if CF == 1 then jmp BB4 else jmp BB7
            ; succ: [BB4, BB6]

            ; pred: [BB5]
            BB6: ; [loop tail]
                jmp BB7
            ; succ: [BB7]

            ; pred: [BB4, BB8]
            BB9: ; [merge]
                v_v4 = ϕ(BB4: v_v2, BB8: v_v3)

                jmp BB5
            ; succ: [BB5]
        """).strip()
        self.assert_ir(src, expected_ir)

    def test_hoist_before_break(self):
        src = """
            func main() -> int {
                v int = 0;
                N int = 0;
                for (i int = 0; i < 10; i = i + 1) {
                    v = 2;  // should be hoisted
                    if (N == 0) {
                        break;
                    }
                    v = 4;  // shouldn't be hoisted
                }
                return v;
            }

            func foo() -> int {
                return -42;
            }        
        """

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                v_v1 = 0
                N_v1 = 0
                jmp BB2
            ; succ: [BB2]

            ; pred: [BB0]
            BB2: ; [condition check]
                i_v1 = 0
                %0_v1 = i_v1 &lt; 10
                cmp(%0_v1, 1)
                if CF == 1 then jmp BB3 else jmp BB7
            ; succ: [BB3, BB7]

            ; pred: [BB2, BB6]
            BB7: ; [loop exit]
                v_v2 = ϕ(BB2: v_v1, BB6: v_v5)

                return(v_v2)
            ; succ: [BB1]

            ; pred: [BB7]
            BB1: ; [exit]
            ; succ: []

            ; pred: [BB2]
            BB3: ; [loop preheader]
                v_v3 = 2
                %3_v1 = N_v1 == 0
                jmp BB4
            ; succ: [BB4]

            ; pred: [BB3, BB5]
            BB4: ; [loop header]
                i_v2 = ϕ(BB3: i_v1, BB5: i_v3)

                cmp(%3_v1, 1)
                if CF == 1 then jmp BB8 else jmp BB9
            ; succ: [BB9, BB8]

            ; pred: [BB4]
            BB8: ; [then]
                jmp BB6
            ; succ: [BB6]

            ; pred: [BB8, BB5]
            BB6: ; [loop tail]
                v_v5 = ϕ(BB5: v_v4, BB8: v_v3)

                jmp BB7
            ; succ: [BB7]

            ; pred: [BB4]
            BB9: ; [merge]
                v_v4 = 4
                jmp BB5
            ; succ: [BB5]

            ; pred: [BB9]
            BB5: ; [loop update]
                i_v3 = i_v2 + 1
                %8_v1 = i_v3 &lt; 10
                cmp(%8_v1, 1)
                if CF == 1 then jmp BB4 else jmp BB7
            ; succ: [BB4, BB6]
        """).strip()
        self.assert_ir(src, expected_ir)

    def test_complicated_hoist(self):
        src = self.make_main("""
            for (i int = 0; i < 10; i = i + 1) {
                
            }
        """)

        expected_ir = textwrap.dedent("""
        """).strip()
        self.assert_ir(src, expected_ir)

    # def test_hoist_with_outside_variables(self):
    #     """Test hoisting operations that depend on variables defined outside the loop."""
    #     src = self.make_main("""
    #     x int = 5;
    #     y int = 10;
    #     for (i int = 0; i < 10; i = i + 1) {
    #         a int = x + y;
    #     }
    #     return 0;
    #     """)
    #
    #     expected_ir = textwrap.dedent("""
    #     """).strip()
    #     self.assert_ir(src, expected_ir)
    #
    # def test_no_hoist_loop_variable(self):
    #     """Test that operations depending on loop variables are NOT hoisted."""
    #     src = self.make_main("""
    #     x int = 5;
    #     for (i int = 0; i < 10; i = i + 1) {
    #         a int = i + x;
    #     }
    #     return 0;
    #     """)
    #
    #     expected_ir = textwrap.dedent("""
    #     """).strip()
    #     self.assert_ir(src, expected_ir)
    #
    # def test_cascading_hoist(self):
    #     """Test cascading hoisting where one hoisted instruction makes another hoistable."""
    #     src = self.make_main("""
    #     x int = 5;
    #     y int = 10;
    #     for (i int = 0; i < 10; i = i + 1) {
    #         a int = x + y;
    #         b int = a * 2;
    #     }
    #     return 0;
    #     """)
    #
    #     expected_ir = textwrap.dedent("""
    #     """).strip()
    #     self.assert_ir(src, expected_ir)
    #
    # def test_mixed_hoistable_and_non_hoistable(self):
    #     """Test a loop with both hoistable and non-hoistable instructions."""
    #     src = self.make_main("""
    #     x int = 5;
    #     for (i int = 0; i < 10; i = i + 1) {
    #         a int = x * 2;
    #         b int = i + 1;
    #         c int = a + b;
    #     }
    #     return 0;
    #     """)
    #
    #     expected_ir = textwrap.dedent("""
    #     """).strip()
    #     self.assert_ir(src, expected_ir)
