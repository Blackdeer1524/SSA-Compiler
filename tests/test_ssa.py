import textwrap
from tests import base


class TestSSA(base.TestBase):
    def __init__(self, *args):
        passes = []
        super().__init__(passes, *args)

    def test_loop_var_init_assign(self):
        src = self.make_main("""
            let i int = 10;
            for (let j int = i; j < 10; j = j + 1) {
            }
            return 0;
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                i_v1 = 10
                jmp BB2
            ; succ: [BB2]

            ; pred: [BB0]
            BB2: ; [condition check]
                j_v1 = i_v1
                %0_v1 = j_v1 < 10
                cmp(%0_v1, 1)
                if CF == 1 then jmp BB3 else jmp BB7
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
            BB4: ; [loop header]
                j_v2 = ϕ(BB3: j_v1, BB5: j_v3)

                jmp BB5
            ; succ: [BB5]

            ; pred: [BB4]
            BB5: ; [loop update]
                j_v3 = j_v2 + 1
                %5_v1 = j_v3 < 10
                cmp(%5_v1, 1)
                if CF == 1 then jmp BB4 else jmp BB6
            ; succ: [BB4, BB6]

            ; pred: [BB5]
            BB6: ; [loop tail]
                jmp BB7
            ; succ: [BB7]
        """).strip()

        self.assert_ir(src, expected_ir)

    def test_proper_phi_placement(self):
        src = """
            func main() -> int {
                let A [64]int = {};
                for (let i int = 0; i < 64; i = i + 1) {
                    A[i] = 10; 
                }
            }
        """

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                (<~)A_v1 = array_init([64])
                jmp BB2
            ; succ: [BB2]

            ; pred: [BB0]
            BB2: ; [condition check]
                i_v1 = 0
                %0_v1 = i_v1 < 64
                cmp(%0_v1, 1)
                if CF == 1 then jmp BB3 else jmp BB7
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
            BB4: ; [loop header]
                i_v2 = ϕ(BB3: i_v1, BB5: i_v3)

                %4_v1 = i_v2 * 1
                %5_v1 = 0 + %4_v1
                (A_v1<~)%6_v1 = %5_v1 + (<~)A_v1
                Store((A_v1<~)%6_v1, 10)
                jmp BB5
            ; succ: [BB5]

            ; pred: [BB4]
            BB5: ; [loop update]
                i_v3 = i_v2 + 1
                %10_v1 = i_v3 < 64
                cmp(%10_v1, 1)
                if CF == 1 then jmp BB4 else jmp BB6
            ; succ: [BB4, BB6]

            ; pred: [BB5]
            BB6: ; [loop tail]
                jmp BB7
            ; succ: [BB7]
        """).strip()

        self.assert_ir(src, expected_ir)

    def test_gauss(self):
        src = """
        func main(A [64][64]int, b [64]int, x [64]int) -> int {
            for (let i int = 0; i < 64; i = i + 1) {
                let pivot int = A[i][i];
                if (pivot == 0) {
                    return -1; 
                }

                for (let j int = i + 1; j < 64; j = j + 1) {
                    let factor int = A[j][i];
                    for (let k int = i; k < 64; k = k + 1) {
                        A[j][k] = A[j][k] * pivot - A[i][k] * factor;
                    }
                    b[j] = b[j] * pivot - b[i] * factor;
                }
            }

            for (let i int = 64 - 1; i >= 0; i = i - 1) {
                let sum int = 0;
                for (let j int = i + 1; j < 64; j = j + 1) {
                    sum = sum + A[i][j] * x[j];
                }
                if (A[i][i] == 0) {
                    return -1; // Singular
                }
                x[i] = (b[i] - sum) / A[i][i];
            }
            return 0;
        }
        """

        expected_ir = textwrap.dedent("""
        """).strip()

        self.assert_ir(src, expected_ir)
