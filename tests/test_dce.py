import textwrap

from src.optimizations.dce import DCE
from tests import base


class TestDCE(base.TestBase):
    def __init__(self, *args):
        passes = [DCE]
        super().__init__(passes, *args)

    def test_simple(self):
        src = self.make_main("""
        let a int = 0;
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
        let a int = 0;
        for (let i int = 0; i < 10; i = i + 1) {
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
            BB2: ; [condition check]
                i_v1 = 0
                %0_v1 = i_v1 < 10
                cmp(%0_v1, 0)
                if CF == 0 then jmp BB3 else jmp BB7
            ; succ: [BB3, BB7]

            ; pred: [BB2, BB6]
            BB7: ; [loop exit]
                return(1)
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
                i_v2 = ϕ(BB3: i_v1, BB5: i_v3)

                jmp BB5
            ; succ: [BB5]

            ; pred: [BB4]
            BB5: ; [loop latch]
                i_v3 = i_v2 + 1
                %7_v1 = i_v3 < 10
                cmp(%7_v1, 0)
                if CF == 0 then jmp BB4 else jmp BB6
            ; succ: [BB4, BB6]

            ; pred: [BB5]
            BB6: ; [loop tail]
                jmp BB7
            ; succ: [BB7]
        """).strip()

        self.assert_ir(src, expected_ir)

    def test_dead_reassign(self):
        src = self.make_main("""
            let a int = 1;
            if (a == 1) { 
                a = 3;
            }
            
            a = 12;  // unused let -> dead code
            return 1;
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                a_v1 = 1
                %0_v1 = a_v1 == 1
                cmp(%0_v1, 0)
                if CF == 0 then jmp BB2 else jmp BB3
            ; succ: [BB2, BB3]

            ; pred: [BB0, BB2]
            BB3: ; [merge]
                return(1)
            ; succ: [BB1]

            ; pred: [BB3]
            BB1: ; [exit]
            ; succ: []

            ; pred: [BB0]
            BB2: ; [then]
                jmp BB3
            ; succ: [BB3]
        """).strip()

        self.assert_ir(src, expected_ir)

    def test_dead_array_init(self):
        src = self.make_main("""
            let arr [64]int = {};
            return 0;
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                return(0)
            ; succ: [BB1]

            ; pred: [BB0]
            BB1: ; [exit]
            ; succ: []
        """).strip()

        self.assert_ir(src, expected_ir)

    def test_dead_array_store(self):
        src = self.make_main("""
            let arr [64]int = {};
            arr[0] = 42;
            arr[10] = 100;
            return 0;
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                return(0)
            ; succ: [BB1]

            ; pred: [BB0]
            BB1: ; [exit]
            ; succ: []
        """).strip()

        self.assert_ir(src, expected_ir)

    def test_dead_array_load(self):
        src = self.make_main("""
            let arr [64]int = {};
            let x int = arr[0];
            let y int = arr[10];
            return 0;
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                return(0)
            ; succ: [BB1]

            ; pred: [BB0]
            BB1: ; [exit]
            ; succ: []
        """).strip()

        self.assert_ir(src, expected_ir)

    def test_dead_unary_operation(self):
        src = self.make_main("""
            let a int = 5;
            let b int = -a;
            let c int = !a;
            return 0;
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                return(0)
            ; succ: [BB1]

            ; pred: [BB0]
            BB1: ; [exit]
            ; succ: []
        """).strip()

        self.assert_ir(src, expected_ir)

    def test_dead_phi_with_dead_incoming(self):
        src = self.make_main("""
            let a int = 0;
            if (a == 0) {
                a = 10;
            } else {
                a = 20;
            }
            let b int = a;
            return 0;
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                a_v1 = 0
                %0_v1 = a_v1 == 0
                cmp(%0_v1, 0)
                if CF == 0 then jmp BB2 else jmp BB4
            ; succ: [BB2, BB4]

            ; pred: [BB0]
            BB4: ; [else]
                jmp BB3
            ; succ: [BB3]

            ; pred: [BB4, BB2]
            BB3: ; [merge]
                return(0)
            ; succ: [BB1]

            ; pred: [BB3]
            BB1: ; [exit]
            ; succ: []

            ; pred: [BB0]
            BB2: ; [then]
                jmp BB3
            ; succ: [BB3] 
        """).strip()

        self.assert_ir(src, expected_ir)

    def test_dead_nested_loop(self):
        src = self.make_main("""
            let a int = 0;
            for (let i int = 0; i < 10; i = i + 1) {
                for (let j int = 0; j < 10; j = j + 1) {
                    a = a + 1;
                }
            }
            return 0;
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                jmp BB2
            ; succ: [BB2]

            ; pred: [BB0]
            BB2: ; [condition check]
                i_v1 = 0
                %0_v1 = i_v1 < 10
                cmp(%0_v1, 0)
                if CF == 0 then jmp BB3 else jmp BB7
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
                jmp BB4
            ; succ: [BB4]

            ; pred: [BB3, BB5]
            BB4: ; [loop body]
                i_v2 = ϕ(BB3: i_v1, BB5: i_v3)

                jmp BB8
            ; succ: [BB8]

            ; pred: [BB4]
            BB8: ; [condition check]
                j_v1 = 0
                %3_v1 = j_v1 < 10
                cmp(%3_v1, 0)
                if CF == 0 then jmp BB9 else jmp BB13
            ; succ: [BB9, BB13]

            ; pred: [BB8, BB12]
            BB13: ; [loop exit]
                jmp BB5
            ; succ: [BB5]

            ; pred: [BB13]
            BB5: ; [loop latch]
                i_v3 = i_v2 + 1
                %15_v1 = i_v3 < 10
                cmp(%15_v1, 0)
                if CF == 0 then jmp BB4 else jmp BB6
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
            BB11: ; [loop latch]
                j_v3 = j_v2 + 1
                %10_v1 = j_v3 < 10
                cmp(%10_v1, 0)
                if CF == 0 then jmp BB10 else jmp BB12
            ; succ: [BB10, BB12]

            ; pred: [BB11]
            BB12: ; [loop tail]
                jmp BB13
            ; succ: [BB13]
        """).strip()

        self.assert_ir(src, expected_ir)

    def test_dead_after_return(self):
        src = self.make_main("""
            let a int = 5;
            return 0;
            a = 10;
            let b int = a + 1;
            return b;
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                return(0)
            ; succ: [BB1]

            ; pred: [BB0]
            BB1: ; [exit]
            ; succ: [] 
        """).strip()

        self.assert_ir(src, expected_ir)

    def test_dead_complex_expression(self):
        src = self.make_main("""
            let a int = 5;
            let b int = 10;
            let c int = (a + b) * 2;
            let d int = c - a;
            return 0;
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                return(0)
            ; succ: [BB1]

            ; pred: [BB0]
            BB1: ; [exit]
            ; succ: [] 
        """).strip()

        self.assert_ir(src, expected_ir)

    def test_dead_phi_chain(self):
        src = self.make_main("""
            let a int = 0;
            let b int = 0;
            for (let i int = 0; i < 10; i = i + 1) {
                a = a + 1;
                b = a;
            }
            return 0;
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                jmp BB2
            ; succ: [BB2]

            ; pred: [BB0]
            BB2: ; [condition check]
                i_v1 = 0
                %0_v1 = i_v1 < 10
                cmp(%0_v1, 0)
                if CF == 0 then jmp BB3 else jmp BB7
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
                jmp BB4
            ; succ: [BB4]

            ; pred: [BB3, BB5]
            BB4: ; [loop body]
                i_v2 = ϕ(BB3: i_v1, BB5: i_v3)

                jmp BB5
            ; succ: [BB5]

            ; pred: [BB4]
            BB5: ; [loop latch]
                i_v3 = i_v2 + 1
                %7_v1 = i_v3 < 10
                cmp(%7_v1, 0)
                if CF == 0 then jmp BB4 else jmp BB6
            ; succ: [BB4, BB6]

            ; pred: [BB5]
            BB6: ; [loop tail]
                jmp BB7
            ; succ: [BB7] 
        """).strip()

        self.assert_ir(src, expected_ir)

    def test_dead_binary_operations(self):
        src = """
        func main() -> int {
            let a int = input();
            let b int = input();
            let c int = a + b;
            let d int = a * b;
            let e int = a - b;
            let f int = a / b;  // not dead, potential division-by-zero -> side effectful
            let g int = a % b;  // not dead, potential modulo zero -> side effectful
            return 0;
        }

        func input() -> int { 
            return 42;
        }
        """

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                a_v1 = input()
                b_v1 = input()
                f_v1 = a_v1 / b_v1
                g_v1 = a_v1 % b_v1
                return(0)
            ; succ: [BB1]
            
            ; pred: [BB0]
            BB1: ; [exit]
            ; succ: []
        """).strip()

        self.assert_ir(src, expected_ir)

    def test_dead_array_multi_dim(self):
        src = self.make_main("""
            let matrix [64][64]int = {};
            matrix[0][0] = 1;
            let x int = matrix[0][0];
            return 0;
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                return(0)
            ; succ: [BB1]

            ; pred: [BB0]
            BB1: ; [exit]
            ; succ: []
        """).strip()

        self.assert_ir(src, expected_ir)

    def test_live_array(self):
        src = """
        func main() -> int {
            let arr [10]int = {};
            if (1) {
                // not dead!
                arr[0] = 1;  
            } 
            return arr[1];
        }
        """

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                (<~)arr_v1 = array_init([10])
                cmp(1, 0)
                if CF == 0 then jmp BB2 else jmp BB3
            ; succ: [BB2, BB3]

            ; pred: [BB0, BB2]
            BB3: ; [merge]
                %8_v1 = 1 * 1
                (arr_v1<~)%9_v1 = (<~)arr_v1 + %8_v1
                %5_v1 = Load((arr_v1<~)%9_v1)
                return(%5_v1)
            ; succ: [BB1]

            ; pred: [BB3]
            BB1: ; [exit]
            ; succ: []

            ; pred: [BB0]
            BB2: ; [then]
                %2_v1 = 0 * 1
                (arr_v1<~)%3_v1 = (<~)arr_v1 + %2_v1
                Store((arr_v1<~)%3_v1, 1)
                jmp BB3
            ; succ: [BB3]
        """).strip()

        self.assert_ir(src, expected_ir)

    def test_dead_array_in_conditional_(self):
        src = """
        func main() -> int {
            let arr [64]int = {};
            let x int = 0;
            if (x == 0) {
                arr[0] = 42;
                let y int = arr[0];
            } else {
                arr[10] = 100;
            }
            return 0;
        }
        """

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                x_v1 = 0
                %0_v1 = x_v1 == 0
                cmp(%0_v1, 0)
                if CF == 0 then jmp BB2 else jmp BB4
            ; succ: [BB2, BB4]

            ; pred: [BB0]
            BB4: ; [else]
                jmp BB3
            ; succ: [BB3]

            ; pred: [BB4, BB2]
            BB3: ; [merge]
                return(0)
            ; succ: [BB1]

            ; pred: [BB3]
            BB1: ; [exit]
            ; succ: []

            ; pred: [BB0]
            BB2: ; [then]
                jmp BB3
            ; succ: [BB3]
        """).strip()

        self.assert_ir(src, expected_ir)

    def test_dead_code_in_one_branch(self):
        src = self.make_main("""
            let a int = 1;
            if (a == 1) {
                let b int = 10;
                let c int = b + 5;
            } else {
                return 1;
            }
            return 0;
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                a_v1 = 1
                %0_v1 = a_v1 == 1
                cmp(%0_v1, 0)
                if CF == 0 then jmp BB2 else jmp BB4
            ; succ: [BB2, BB4]

            ; pred: [BB0]
            BB4: ; [else]
                return(1)
            ; succ: [BB1]

            ; pred: [BB4, BB3]
            BB1: ; [exit]
            ; succ: []

            ; pred: [BB0]
            BB2: ; [then]
                jmp BB3
            ; succ: [BB3]

            ; pred: [BB2]
            BB3: ; [merge]
                return(0)
            ; succ: [BB1]
        """).strip()

        self.assert_ir(src, expected_ir)

    def test_dead_loop_with_phi(self):
        src = self.make_main("""
            let sum int = 0;
            for (let i int = 0; i < 10; i = i + 1) {
                sum = sum + i;
            }
            return 0;
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                jmp BB2
            ; succ: [BB2]

            ; pred: [BB0]
            BB2: ; [condition check]
                i_v1 = 0
                %0_v1 = i_v1 < 10
                cmp(%0_v1, 0)
                if CF == 0 then jmp BB3 else jmp BB7
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
                jmp BB4
            ; succ: [BB4]

            ; pred: [BB3, BB5]
            BB4: ; [loop body]
                i_v2 = ϕ(BB3: i_v1, BB5: i_v3)

                jmp BB5
            ; succ: [BB5]

            ; pred: [BB4]
            BB5: ; [loop latch]
                i_v3 = i_v2 + 1
                %7_v1 = i_v3 < 10
                cmp(%7_v1, 0)
                if CF == 0 then jmp BB4 else jmp BB6
            ; succ: [BB4, BB6]

            ; pred: [BB5]
            BB6: ; [loop tail]
                jmp BB7
            ; succ: [BB7] 
        """).strip()

        self.assert_ir(src, expected_ir)

    def test_array_dce_loop(self):
        src = """
        func main() -> void {
            let a [5]int = {};
            for (let i int = 0; i < 10; i = i + 1) {
                a[i] = i;
                foo_5(a);
                a[i] = i * i;
            }
        }
        
        func foo_5(x [5]int) -> void {
        }
        """

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                (<~)a_v1 = array_init([5])
                jmp BB2
            ; succ: [BB2]

            ; pred: [BB0]
            BB2: ; [condition check]
                i_v1 = 0
                %0_v1 = i_v1 < 10
                cmp(%0_v1, 0)
                if CF == 0 then jmp BB3 else jmp BB7
            ; succ: [BB3, BB7]

            ; pred: [BB2, BB6]
            BB7: ; [loop exit]
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
                i_v2 = ϕ(BB3: i_v1, BB5: i_v3)

                %4_v1 = i_v2 * 1
                (a_v1<~)%5_v1 = (<~)a_v1 + %4_v1
                Store((a_v1<~)%5_v1, i_v2)
                %7_v1 = foo_5((<~)a_v1)
                %10_v1 = i_v2 * 1
                (a_v1<~)%11_v1 = (<~)a_v1 + %10_v1
                %12_v1 = i_v2 * i_v2
                Store((a_v1<~)%11_v1, %12_v1)
                jmp BB5
            ; succ: [BB5]

            ; pred: [BB4]
            BB5: ; [loop latch]
                i_v3 = i_v2 + 1
                %17_v1 = i_v3 < 10
                cmp(%17_v1, 0)
                if CF == 0 then jmp BB4 else jmp BB6
            ; succ: [BB4, BB6]

            ; pred: [BB5]
            BB6: ; [loop tail]
                jmp BB7
            ; succ: [BB7]
        """).strip()

        self.assert_ir(src, expected_ir)

    def test_dce_args(self):
        src = """
        func main(A [64][64]int, b [64]int, x [64]int) -> int {
            A[1][1] = 1;
            return 0;
        }
        """

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                (<~)A_v1 = getarg(0)
                (<~)b_v1 = getarg(1)
                (<~)x_v1 = getarg(2)
                %1_v1 = 1 * 64
                %3_v1 = 1 * 1
                %4_v1 = %1_v1 + %3_v1
                (A_v1<~)%5_v1 = (<~)A_v1 + %4_v1
                Store((A_v1<~)%5_v1, 1)
                return(0)
            ; succ: [BB1]

            ; pred: [BB0]
            BB1: ; [exit]
            ; succ: []
        """).strip()

        self.assert_ir(src, expected_ir)

    def test_loop_array_write(self):
        src = """
        func main() -> int {
            let a [8]int = {};
            for {
                foo(a);
                if (bar()) {   
                    a[5] = 10;  // live
                }
                
                if (a[1] == 2) {
                    break;
                }
            }
            
            return 0;
        }
        
        func bar() -> int {
            return 123; // random value
        }

        func foo (a [8]int) -> void {
        }
        """

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                (<~)a_v1 = array_init([8])
                jmp BB2
            ; succ: [BB2]

            ; pred: [BB0]
            BB2: ; [uncond loop preheader]
                jmp BB3
            ; succ: [BB3]

            ; pred: [BB2, BB4]
            BB3: ; [uncond loop body]
                %0_v1 = foo((<~)a_v1)
                %2_v1 = bar()
                cmp(%2_v1, 0)
                if CF == 0 then jmp BB7 else jmp BB8
            ; succ: [BB7, BB8]

            ; pred: [BB3, BB7]
            BB8: ; [merge]
                %11_v1 = 1 * 1
                (a_v1<~)%12_v1 = (<~)a_v1 + %11_v1
                %8_v1 = Load((a_v1<~)%12_v1)
                %7_v1 = %8_v1 == 2
                cmp(%7_v1, 0)
                if CF == 0 then jmp BB9 else jmp BB10
            ; succ: [BB9, BB10]

            ; pred: [BB8]
            BB10: ; [merge]
                jmp BB4
            ; succ: [BB4]

            ; pred: [BB10]
            BB4: ; [uncond loop latch]
                jmp BB3
            ; succ: [BB3]

            ; pred: [BB8]
            BB9: ; [then]
                jmp BB5
            ; succ: [BB5]

            ; pred: [BB9]
            BB5: ; [uncond loop tail]
                jmp BB6
            ; succ: [BB6]

            ; pred: [BB5]
            BB6: ; [uncond loop exit]
                return(0)
            ; succ: [BB1]

            ; pred: [BB6]
            BB1: ; [exit]
            ; succ: []

            ; pred: [BB3]
            BB7: ; [then]
                %4_v1 = 5 * 1
                (a_v1<~)%5_v1 = (<~)a_v1 + %4_v1
                Store((a_v1<~)%5_v1, 10)
                jmp BB8
            ; succ: [BB8]
        """).strip()

        self.assert_ir(src, expected_ir)

    def test_dead_write_with_break(self):
        src = """
        func main() -> int {
            let a [8]int = {};
            for {
                foo(a);
                if (bar()) {   
                    a[5] = 10;  // dead!
                    break;
                }                
            }
            return 0;
        }
        
        func bar() -> int {
            return 123; // random value
        }

        func foo (a [8]int) -> void {
        }
        """

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                (<~)a_v1 = array_init([8])
                jmp BB2
            ; succ: [BB2]

            ; pred: [BB0]
            BB2: ; [uncond loop preheader]
                jmp BB3
            ; succ: [BB3]

            ; pred: [BB2, BB4]
            BB3: ; [uncond loop body]
                %0_v1 = foo((<~)a_v1)
                %2_v1 = bar()
                cmp(%2_v1, 0)
                if CF == 0 then jmp BB7 else jmp BB8
            ; succ: [BB7, BB8]

            ; pred: [BB3]
            BB8: ; [merge]
                jmp BB4
            ; succ: [BB4]

            ; pred: [BB8]
            BB4: ; [uncond loop latch]
                jmp BB3
            ; succ: [BB3]

            ; pred: [BB3]
            BB7: ; [then]
                jmp BB5
            ; succ: [BB5]

            ; pred: [BB7]
            BB5: ; [uncond loop tail]
                jmp BB6
            ; succ: [BB6]

            ; pred: [BB5]
            BB6: ; [uncond loop exit]
                return(0)
            ; succ: [BB1]

            ; pred: [BB6]
            BB1: ; [exit]
            ; succ: [] 
        """).strip()

        self.assert_ir(src, expected_ir)

    def test_nesting_in_loop(self):
        src = """
        func main() -> int {
            let a [8]int = {};
            for {
                foo(a);
                a[4] = 4; // live

                if (bar()) {
                    a[7] = 12;  // dead
                    break;
                }
            }
            return 0;
        }
        
        func bar() -> int {
            return 123; // random value
        }

        func foo (a [8]int) -> void {
        }
        """

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                (<~)a_v1 = array_init([8])
                jmp BB2
            ; succ: [BB2]

            ; pred: [BB0]
            BB2: ; [uncond loop preheader]
                jmp BB3
            ; succ: [BB3]

            ; pred: [BB2, BB4]
            BB3: ; [uncond loop body]
                %0_v1 = foo((<~)a_v1)
                %3_v1 = 4 * 1
                (a_v1<~)%4_v1 = (<~)a_v1 + %3_v1
                Store((a_v1<~)%4_v1, 4)
                %6_v1 = bar()
                cmp(%6_v1, 0)
                if CF == 0 then jmp BB7 else jmp BB8
            ; succ: [BB7, BB8]

            ; pred: [BB3]
            BB8: ; [merge]
                jmp BB4
            ; succ: [BB4]

            ; pred: [BB8]
            BB4: ; [uncond loop latch]
                jmp BB3
            ; succ: [BB3]

            ; pred: [BB3]
            BB7: ; [then]
                jmp BB5
            ; succ: [BB5]

            ; pred: [BB7]
            BB5: ; [uncond loop tail]
                jmp BB6
            ; succ: [BB6]

            ; pred: [BB5]
            BB6: ; [uncond loop exit]
                return(0)
            ; succ: [BB1]

            ; pred: [BB6]
            BB1: ; [exit]
            ; succ: [] 
        """).strip()

        self.assert_ir(src, expected_ir)

    def test_continuous_simple(self):
        src = """
        func main() -> int {
            let a [10]int = {};
            
            a[0] = 1;
            foo(a);
            
            if (1) {
                a[2] = 3; // dead
            }
            return 0;
        }

        func foo (a [10]int) -> void {
        }
        """

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                (<~)a_v1 = array_init([10])
                %1_v1 = 0 * 1
                (a_v1<~)%2_v1 = (<~)a_v1 + %1_v1
                Store((a_v1<~)%2_v1, 1)
                %4_v1 = foo((<~)a_v1)
                cmp(1, 0)
                if CF == 0 then jmp BB2 else jmp BB3
            ; succ: [BB2, BB3]

            ; pred: [BB0, BB2]
            BB3: ; [merge]
                return(0)
            ; succ: [BB1]

            ; pred: [BB3]
            BB1: ; [exit]
            ; succ: []

            ; pred: [BB0]
            BB2: ; [then]
                jmp BB3
            ; succ: [BB3]        
        """).strip()

        self.assert_ir(src, expected_ir)
