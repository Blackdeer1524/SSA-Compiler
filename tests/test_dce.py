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
                %0_v1 = i_v1 &lt; 10
                cmp(%0_v1, 1)
                if CF == 1 then jmp BB3 else jmp BB7
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
            BB4: ; [loop header]
                i_v2 = ϕ(BB3: i_v1, BB5: i_v3)

                jmp BB5
            ; succ: [BB5]

            ; pred: [BB4]
            BB5: ; [loop update]
                i_v3 = i_v2 + 1
                %7_v1 = i_v3 &lt; 10
                cmp(%7_v1, 1)
                if CF == 1 then jmp BB4 else jmp BB7
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

        expected_ir = textwrap.dedent("""""").strip()

        self.assert_ir(src, expected_ir)

    def test_dead_array_load(self):
        src = self.make_main("""
            let arr [64]int = {};
            let x int = arr[0];
            let y int = arr[10];
            return 0;
        """)

        expected_ir = textwrap.dedent("""""").strip()

        self.assert_ir(src, expected_ir)

    def test_dead_unary_operation(self):
        src = self.make_main("""
            let a int = 5;
            let b int = -a;
            let c int = !a;
            return 0;
        """)

        expected_ir = textwrap.dedent("""""").strip()

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

        expected_ir = textwrap.dedent("""""").strip()

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

        expected_ir = textwrap.dedent("""""").strip()

        self.assert_ir(src, expected_ir)

    def test_dead_after_return(self):
        src = self.make_main("""
            let a int = 5;
            return 0;
            a = 10;
            let b int = a + 1;
            return b;
        """)

        expected_ir = textwrap.dedent("""""").strip()

        self.assert_ir(src, expected_ir)

    def test_dead_complex_expression(self):
        src = self.make_main("""
            let a int = 5;
            let b int = 10;
            let c int = (a + b) * 2;
            let d int = c - a;
            return 0;
        """)

        expected_ir = textwrap.dedent("""""").strip()

        self.assert_ir(src, expected_ir)

    def test_dead_array_in_conditional(self):
        src = self.make_main("""
            let arr [64]int = {};
            let x int = 0;
            if (x == 0) {
                arr[0] = 42;
                let y int = arr[0];
            } else {
                arr[10] = 100;
            }
            return 0;
        """)

        expected_ir = textwrap.dedent("""""").strip()

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

        expected_ir = textwrap.dedent("""""").strip()

        self.assert_ir(src, expected_ir)

    def test_dead_binary_operations(self):
        src = self.make_main("""
            let a int = 5;
            let b int = 10;
            let c int = a + b;
            let d int = a * b;
            let e int = a - b;
            let f int = a / b;
            return 0;
        """)

        expected_ir = textwrap.dedent("""""").strip()

        self.assert_ir(src, expected_ir)

    def test_dead_array_multi_dim(self):
        src = self.make_main("""
            let matrix [64][64]int = {};
            matrix[0][0] = 1;
            let x int = matrix[0][0];
            return 0;
        """)

        expected_ir = textwrap.dedent("""""").strip()

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

        expected_ir = textwrap.dedent("""""").strip()

        self.assert_ir(src, expected_ir)

    def test_dead_loop_with_phi(self):
        src = self.make_main("""
            let sum int = 0;
            for (let i int = 0; i < 10; i = i + 1) {
                sum = sum + i;
            }
            return 0;
        """)

        expected_ir = textwrap.dedent("""""").strip()

        self.assert_ir(src, expected_ir)
