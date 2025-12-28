import textwrap
from tests import base

from src.optimizations.licm import LICM
from src.optimizations.sccp import SCCP
from src.optimizations.dce import DCE


class TestEndToEnd(base.TestBase):
    def __init__(self, *args):
        passes = [SCCP, DCE, LICM]
        super().__init__(passes, *args)

    def test_matmul(self):
        src = """
        func mat_vec_mul(mat [64][64]int, vec [64]int, result [64]int) -> void {
            for (let i int = 0; i < 64; i = i + 1) {
                let sum int = 0;
                for (let j int = 0; j < 64; j = j + 1) {
                    sum = sum + mat[i][j] * vec[j];
                }
                result[i] = sum;
            }
        }
        """

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                (<~)mat_v1 = getarg(0)
                (<~)vec_v1 = getarg(1)
                (<~)result_v1 = getarg(2)
                jmp BB2
            ; succ: [BB2]

            ; pred: [BB0]
            BB2: ; [condition check]
                jmp BB3
            ; succ: [BB3]

            ; pred: [BB2]
            BB3: ; [loop preheader]
                jmp BB4
            ; succ: [BB4]

            ; pred: [BB3, BB5]
            BB4: ; [loop body]
                i_v2 = ϕ(BB3: 0, BB5: i_v3)

                jmp BB8
            ; succ: [BB8]

            ; pred: [BB4]
            BB8: ; [condition check]
                jmp BB9
            ; succ: [BB9]

            ; pred: [BB8]
            BB9: ; [loop preheader]
                %11_v1 = i_v2 * 64
                jmp BB10
            ; succ: [BB10]

            ; pred: [BB9, BB11]
            BB10: ; [loop body]
                sum_v3 = ϕ(BB9: 0, BB11: sum_v4)
                j_v2 = ϕ(BB9: 0, BB11: j_v3)

                %13_v1 = j_v2 * 1
                %14_v1 = %11_v1 + %13_v1
                (mat_v1<~)%15_v1 = (<~)mat_v1 + %14_v1
                %8_v1 = Load((mat_v1<~)%15_v1)
                %19_v1 = j_v2 * 1
                (vec_v1<~)%20_v1 = (<~)vec_v1 + %19_v1
                %16_v1 = Load((vec_v1<~)%20_v1)
                %7_v1 = %8_v1 * %16_v1
                sum_v4 = sum_v3 + %7_v1
                jmp BB11
            ; succ: [BB11]

            ; pred: [BB10]
            BB11: ; [loop latch]
                j_v3 = j_v2 + 1
                %23_v1 = j_v3 < 64
                cmp(%23_v1, 0)
                if CF == 0 then jmp BB10 else jmp BB12
            ; succ: [BB10, BB12]

            ; pred: [BB11]
            BB12: ; [loop tail]
                jmp BB13
            ; succ: [BB13]

            ; pred: [BB12]
            BB13: ; [loop exit]
                sum_v2 = ϕ(BB12: sum_v4)

                %27_v1 = i_v2 * 1
                (result_v1<~)%28_v1 = (<~)result_v1 + %27_v1
                Store((result_v1<~)%28_v1, sum_v2)
                jmp BB5
            ; succ: [BB5]

            ; pred: [BB13]
            BB5: ; [loop latch]
                i_v3 = i_v2 + 1
                %32_v1 = i_v3 < 64
                cmp(%32_v1, 0)
                if CF == 0 then jmp BB4 else jmp BB6
            ; succ: [BB4, BB6]

            ; pred: [BB5]
            BB6: ; [loop tail]
                jmp BB7
            ; succ: [BB7]

            ; pred: [BB6]
            BB7: ; [loop exit]
            ; succ: [BB1]

            ; pred: [BB7]
            BB1: ; [exit]
            ; succ: [] 
        """).strip()

        self.assert_ir(src, expected_ir)

    # def test_gauss(self):
    #     src = """
    #     func gauss_solve(A [64][64]int, b [64]int, x [64]int) -> int {
    #         for (let i int = 0; i < 64; i = i + 1) {
    #             let pivot int = A[i][i];
    #             if (pivot == 0) {
    #                 return -1;  // Singular
    #             }
    #
    #             let real_pivot int = A[i][i];
    #             for (let j int = i + 1; j < 64; j = j + 1) {
    #                 let factor int = A[j][i];
    #                 for (let k int = i; k < 64; k = k + 1) {
    #                     A[j][k] = A[j][k] * real_pivot - A[i][k] * factor;
    #                 }
    #                 b[j] = b[j] * real_pivot - b[i] * factor;
    #             }
    #         }
    #
    #         for (let i int = 64 - 1; i >= 0; i = i - 1) {
    #             let sum int = 0;
    #             for (let j int = i + 1; j < 64; j = j + 1) {
    #                 sum = sum + A[i][j] * x[j];
    #             }
    #             if (A[i][i] == 0) {
    #                 return -1; // Singular
    #             }
    #             x[i] = (b[i] - sum) / A[i][i];
    #         }
    #         return 0;
    #     }
    #     """
    #
    #     expected_ir = textwrap.dedent("""
    #     """).strip()
    #
    #     self.assert_ir(src, expected_ir)

    def test_for_loop_with_bad_condition(self):
        src = """
        func main() -> int {
            let N int = 0;
            for (let i int = 0; 1; i = i + 1) {
                for (let j int = 0; j < 10; j = j + 1) {
                }
            }
            return N;
        }
        """

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                jmp BB2
            ; succ: [BB2]

            ; pred: [BB0]
            BB2: ; [condition check]
                jmp BB3
            ; succ: [BB3]

            ; pred: [BB2]
            BB3: ; [loop preheader]
                jmp BB4
            ; succ: [BB4]

            ; pred: [BB3, BB5]
            BB4: ; [loop body]
                jmp BB8
            ; succ: [BB8]

            ; pred: [BB4]
            BB8: ; [condition check]
                jmp BB9
            ; succ: [BB9]

            ; pred: [BB8]
            BB9: ; [loop preheader]
                jmp BB10
            ; succ: [BB10]

            ; pred: [BB9, BB11]
            BB10: ; [loop body]
                j_v2 = ϕ(BB9: 0, BB11: j_v3)

                jmp BB11
            ; succ: [BB11]

            ; pred: [BB10]
            BB11: ; [loop latch]
                j_v3 = j_v2 + 1
                %6_v1 = j_v3 < 10
                cmp(%6_v1, 0)
                if CF == 0 then jmp BB10 else jmp BB12
            ; succ: [BB10, BB12]

            ; pred: [BB11]
            BB12: ; [loop tail]
                jmp BB13
            ; succ: [BB13]

            ; pred: [BB12]
            BB13: ; [loop exit]
                jmp BB5
            ; succ: [BB5]

            ; pred: [BB13]
            BB5: ; [loop latch]
                jmp BB4
            ; succ: [BB4] 
        """).strip()

        self.assert_ir(src, expected_ir)
