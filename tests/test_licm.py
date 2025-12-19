import textwrap
from src.optimizations.licm import LICM
from tests import base


class TestLICM(base.TestBase):
    def __init__(self, *args):
        passes = [LICM]
        super().__init__(passes, *args)

    def test_simple(self):
        src = self.make_main("""
            let a int = 0;
            for (let i int = 0; i < 10; i = i + 1) {
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
                %0_v1 = i_v1 < 10
                cmp(%0_v1, 0)
                if CF == 1 then jmp BB7 else jmp BB3
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
            BB4: ; [loop body]
                i_v2 = ϕ(BB3: i_v1, BB5: i_v3)

                jmp BB5
            ; succ: [BB5]

            ; pred: [BB4]
            BB5: ; [loop update]
                i_v3 = i_v2 + 1
                %5_v1 = i_v3 < 10
                cmp(%5_v1, 0)
                if CF == 1 then jmp BB6 else jmp BB4
            ; succ: [BB4, BB6]

            ; pred: [BB5]
            BB6: ; [loop tail]
                jmp BB7
            ; succ: [BB7]
        """).strip()
        self.assert_ir(src, expected_ir)

    def test_nested_loops(self):
        src = self.make_main("""
            let a int = 0;
            for (let i int = 0; i < 10; i = i + 1) {
                for (let j int = 0; j < 10; j = j + 1) {
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
                %0_v1 = i_v1 < 10
                cmp(%0_v1, 0)
                if CF == 1 then jmp BB7 else jmp BB3
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
                %3_v1 = j_v1 < 10
                jmp BB4
            ; succ: [BB4]

            ; pred: [BB3, BB5]
            BB4: ; [loop body]
                i_v2 = ϕ(BB3: i_v1, BB5: i_v3)

                jmp BB8
            ; succ: [BB8]

            ; pred: [BB4]
            BB8: ; [condition check]
                cmp(%3_v1, 0)
                if CF == 1 then jmp BB13 else jmp BB9
            ; succ: [BB9, BB13]

            ; pred: [BB8, BB12]
            BB13: ; [loop exit]
                jmp BB5
            ; succ: [BB5]

            ; pred: [BB13]
            BB5: ; [loop update]
                i_v3 = i_v2 + 1
                %13_v1 = i_v3 < 10
                cmp(%13_v1, 0)
                if CF == 1 then jmp BB6 else jmp BB4
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
            BB10: ; [loop body]
                j_v2 = ϕ(BB9: j_v1, BB11: j_v3)

                jmp BB11
            ; succ: [BB11]

            ; pred: [BB10]
            BB11: ; [loop update]
                j_v3 = j_v2 + 1
                %8_v1 = j_v3 < 10
                cmp(%8_v1, 0)
                if CF == 1 then jmp BB12 else jmp BB10
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
                let N int = foo(); 
                let x int = 0;
                for (let i int = 0; i < N; i = i + 1) {
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
                %0_v1 = i_v1 < N_v1
                cmp(%0_v1, 0)
                if CF == 1 then jmp BB7 else jmp BB3
            ; succ: [BB3, BB7]

            ; pred: [BB2, BB6]
            BB7: ; [loop exit]
                x_v3 = ϕ(BB2: x_v1, BB6: x_v2)

                return(x_v3)
            ; succ: [BB1]

            ; pred: [BB7]
            BB1: ; [exit]
            ; succ: []

            ; pred: [BB2]
            BB3: ; [loop preheader]
                x_v2 = 11
                jmp BB4
            ; succ: [BB4]

            ; pred: [BB3, BB5]
            BB4: ; [loop body]
                i_v2 = ϕ(BB3: i_v1, BB5: i_v3)

                jmp BB5
            ; succ: [BB5]

            ; pred: [BB4]
            BB5: ; [loop update]
                i_v3 = i_v2 + 1
                %5_v1 = i_v3 < N_v1
                cmp(%5_v1, 0)
                if CF == 1 then jmp BB6 else jmp BB4
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
                let v int = 0;
                for (let i int = 0; i < 10; i = i + 1) {
                    let N int = foo();
                    if (N == 0) {
                        v = 2;  // no hoist
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
                %0_v1 = i_v1 < 10
                cmp(%0_v1, 0)
                if CF == 1 then jmp BB7 else jmp BB3
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
            BB4: ; [loop body]
                v_v2 = ϕ(BB3: v_v1, BB5: v_v4)
                i_v2 = ϕ(BB3: i_v1, BB5: i_v3)

                N_v1 = foo()
                %3_v1 = N_v1 == 0
                cmp(%3_v1, 0)
                if CF == 1 then jmp BB9 else jmp BB8
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
                %8_v1 = i_v3 < 10
                cmp(%8_v1, 0)
                if CF == 1 then jmp BB6 else jmp BB4
            ; succ: [BB4, BB6]

            ; pred: [BB5]
            BB6: ; [loop tail]
                jmp BB7
            ; succ: [BB7]
        """).strip()
        self.assert_ir(src, expected_ir)

    def test_hoist_before_break(self):
        src = """
            func main() -> int {
                let v int = 0;
                let N int = 0;
                for (let i int = 0; i < 10; i = i + 1) {
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
                %0_v1 = i_v1 < 10
                cmp(%0_v1, 0)
                if CF == 1 then jmp BB7 else jmp BB3
            ; succ: [BB3, BB7]

            ; pred: [BB2, BB6]
            BB7: ; [loop exit]
                v_v5 = ϕ(BB2: v_v1, BB6: v_v3)

                return(v_v5)
            ; succ: [BB1]

            ; pred: [BB7]
            BB1: ; [exit]
            ; succ: []

            ; pred: [BB2]
            BB3: ; [loop preheader]
                v_v2 = 2
                %3_v1 = N_v1 == 0
                jmp BB4
            ; succ: [BB4]

            ; pred: [BB3, BB5]
            BB4: ; [loop body]
                i_v2 = ϕ(BB3: i_v1, BB5: i_v3)

                cmp(%3_v1, 0)
                if CF == 1 then jmp BB9 else jmp BB8
            ; succ: [BB9, BB8]

            ; pred: [BB4]
            BB8: ; [then]
                jmp BB6
            ; succ: [BB6]

            ; pred: [BB8, BB5]
            BB6: ; [loop tail]
                v_v3 = ϕ(BB8: v_v2, BB5: v_v4)

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
                %8_v1 = i_v3 < 10
                cmp(%8_v1, 0)
                if CF == 1 then jmp BB6 else jmp BB4
            ; succ: [BB4, BB6]
        """).strip()
        self.assert_ir(src, expected_ir)

    def test_complicated_hoist(self):
        src = """
        func main() -> int {
            let v int = 0;
            for (let i int = 0; i < 10; i = i + 1) {
                v = 2;          // hoist
                let N int = foo();
                if (N == 0) {
                    break;
                }
                let a int = 0;
                for (let j int = 0; j < 10; j = j + 1) {
                    N = 10;     // hoist before break
                    a = N + j;  
                }
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
                %0_v1 = i_v1 < 10
                cmp(%0_v1, 0)
                if CF == 1 then jmp BB7 else jmp BB3
            ; succ: [BB3, BB7]

            ; pred: [BB2, BB6]
            BB7: ; [loop exit]
                v_v3 = ϕ(BB2: v_v1, BB6: v_v2)

                return(v_v3)
            ; succ: [BB1]

            ; pred: [BB7]
            BB1: ; [exit]
            ; succ: []

            ; pred: [BB2]
            BB3: ; [loop preheader]
                v_v2 = 2
                jmp BB4
            ; succ: [BB4]

            ; pred: [BB3, BB5]
            BB4: ; [loop body]
                i_v2 = ϕ(BB3: i_v1, BB5: i_v3)

                N_v1 = foo()
                %3_v1 = N_v1 == 0
                cmp(%3_v1, 0)
                if CF == 1 then jmp BB9 else jmp BB8
            ; succ: [BB9, BB8]

            ; pred: [BB4]
            BB8: ; [then]
                jmp BB6
            ; succ: [BB6]

            ; pred: [BB8, BB5]
            BB6: ; [loop tail]
                jmp BB7
            ; succ: [BB7]

            ; pred: [BB4]
            BB9: ; [merge]
                a_v1 = 0
                jmp BB10
            ; succ: [BB10]

            ; pred: [BB9]
            BB10: ; [condition check]
                j_v1 = 0
                %6_v1 = j_v1 < 10
                cmp(%6_v1, 0)
                if CF == 1 then jmp BB15 else jmp BB11
            ; succ: [BB11, BB15]

            ; pred: [BB10, BB14]
            BB15: ; [loop exit]
                jmp BB5
            ; succ: [BB5]

            ; pred: [BB15]
            BB5: ; [loop update]
                i_v3 = i_v2 + 1
                %18_v1 = i_v3 < 10
                cmp(%18_v1, 0)
                if CF == 1 then jmp BB6 else jmp BB4
            ; succ: [BB4, BB6]

            ; pred: [BB10]
            BB11: ; [loop preheader]
                N_v2 = 10
                jmp BB12
            ; succ: [BB12]

            ; pred: [BB11, BB13]
            BB12: ; [loop body]
                j_v2 = ϕ(BB11: j_v1, BB13: j_v3)

                a_v2 = N_v2 + j_v2
                jmp BB13
            ; succ: [BB13]

            ; pred: [BB12]
            BB13: ; [loop update]
                j_v3 = j_v2 + 1
                %13_v1 = j_v3 < 10
                cmp(%13_v1, 0)
                if CF == 1 then jmp BB14 else jmp BB12
            ; succ: [BB12, BB14]

            ; pred: [BB13]
            BB14: ; [loop tail]
                jmp BB15
            ; succ: [BB15] 
        """).strip()
        self.assert_ir(src, expected_ir)

    def test_cascading_hoist(self):
        src = self.make_main("""
        let x int = 5;
        let y int = 10;
        for (let i int = 0; i < 10; i = i + 1) {
            let a int = x + y;
            let b int = a * 2;
        }
        return 0;
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                x_v1 = 5
                y_v1 = 10
                jmp BB2
            ; succ: [BB2]

            ; pred: [BB0]
            BB2: ; [condition check]
                i_v1 = 0
                %0_v1 = i_v1 < 10
                cmp(%0_v1, 0)
                if CF == 1 then jmp BB7 else jmp BB3
            ; succ: [BB3, BB7]

            ; pred: [BB2, BB6]
            BB7: ; [loop exit]
                return(0)
            ; succ: [BB1]

            ; pred: [BB7]
            BB1: ; [exit]
            ; succ: []

            ; pred: [BB2]
            BB3: ; [loop preheader]
                a_v1 = x_v1 + y_v1
                b_v1 = a_v1 * 2
                jmp BB4
            ; succ: [BB4]

            ; pred: [BB3, BB5]
            BB4: ; [loop body]
                i_v2 = ϕ(BB3: i_v1, BB5: i_v3)

                jmp BB5
            ; succ: [BB5]

            ; pred: [BB4]
            BB5: ; [loop update]
                i_v3 = i_v2 + 1
                %9_v1 = i_v3 < 10
                cmp(%9_v1, 0)
                if CF == 1 then jmp BB6 else jmp BB4
            ; succ: [BB4, BB6]

            ; pred: [BB5]
            BB6: ; [loop tail]
                jmp BB7
            ; succ: [BB7]        
        """).strip()

        self.assert_ir(src, expected_ir)

    def test_mixed_hoistable_and_non_hoistable(self):
        """Test a loop with both hoistable and non-hoistable instructions."""
        src = self.make_main("""
        let x int = 5;
        for (let i int = 0; i < 10; i = i + 1) {
            let a int = x * 2;
            let b int = i + 1;
            let c int = a + b;
        }
        return 0;
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                x_v1 = 5
                jmp BB2
            ; succ: [BB2]

            ; pred: [BB0]
            BB2: ; [condition check]
                i_v1 = 0
                %0_v1 = i_v1 < 10
                cmp(%0_v1, 0)
                if CF == 1 then jmp BB7 else jmp BB3
            ; succ: [BB3, BB7]

            ; pred: [BB2, BB6]
            BB7: ; [loop exit]
                return(0)
            ; succ: [BB1]

            ; pred: [BB7]
            BB1: ; [exit]
            ; succ: []

            ; pred: [BB2]
            BB3: ; [loop preheader]
                a_v1 = x_v1 * 2
                jmp BB4
            ; succ: [BB4]

            ; pred: [BB3, BB5]
            BB4: ; [loop body]
                i_v2 = ϕ(BB3: i_v1, BB5: i_v3)

                b_v1 = i_v2 + 1
                c_v1 = a_v1 + b_v1
                jmp BB5
            ; succ: [BB5]

            ; pred: [BB4]
            BB5: ; [loop update]
                i_v3 = i_v2 + 1
                %11_v1 = i_v3 < 10
                cmp(%11_v1, 0)
                if CF == 1 then jmp BB6 else jmp BB4
            ; succ: [BB4, BB6]

            ; pred: [BB5]
            BB6: ; [loop tail]
                jmp BB7
            ; succ: [BB7] 
        """).strip()

        self.assert_ir(src, expected_ir)

    def test_array_load_move(self):
        src = self.make_main("""
        let a [10]int = {};
        let x int = 0;
        for (let i int = 0; i < 10; i = i + 1) {
            a[i] = i;
            x = a[5];
        }
        return x;
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                (<~)a_v1 = array_init([10])
                x_v1 = 0
                jmp BB2
            ; succ: [BB2]

            ; pred: [BB0]
            BB2: ; [condition check]
                i_v1 = 0
                %0_v1 = i_v1 < 10
                cmp(%0_v1, 0)
                if CF == 1 then jmp BB7 else jmp BB3
            ; succ: [BB3, BB7]

            ; pred: [BB2, BB6]
            BB7: ; [loop exit]
                x_v3 = ϕ(BB2: x_v1, BB6: x_v2)

                return(x_v3)
            ; succ: [BB1]

            ; pred: [BB7]
            BB1: ; [exit]
            ; succ: []

            ; pred: [BB2]
            BB3: ; [loop preheader]
                %9_v1 = 5 * 1
                (a_v1<~)%10_v1 = (<~)a_v1 + %9_v1
                jmp BB4
            ; succ: [BB4]

            ; pred: [BB3, BB5]
            BB4: ; [loop body]
                i_v2 = ϕ(BB3: i_v1, BB5: i_v3)

                %4_v1 = i_v2 * 1
                (a_v1<~)%5_v1 = (<~)a_v1 + %4_v1
                Store((a_v1<~)%5_v1, i_v2)
                x_v2 = Load((a_v1<~)%10_v1)
                jmp BB5
            ; succ: [BB5]

            ; pred: [BB4]
            BB5: ; [loop update]
                i_v3 = i_v2 + 1
                %13_v1 = i_v3 < 10
                cmp(%13_v1, 0)
                if CF == 1 then jmp BB6 else jmp BB4
            ; succ: [BB4, BB6]

            ; pred: [BB5]
            BB6: ; [loop tail]
                jmp BB7
            ; succ: [BB7] 
        """).strip()
        self.assert_ir(src, expected_ir)
