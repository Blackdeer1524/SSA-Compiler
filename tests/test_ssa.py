import textwrap
from tests import base


class TestSSA(base.TestBase):
    def __init__(self, *args):
        passes = []
        super().__init__(passes, *args)

    def test_for_loop_gen(self):
        src = self.make_main("""
            for (let j int = 0; j < 10; j = j + 1) {
                if (j + 1 == 6) {
                    continue;
                }
                
                if (j == 7) {
                    break;
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
                j_v1 = 0
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

                %4_v1 = j_v2 + 1
                %3_v1 = %4_v1 == 6
                cmp(%3_v1, 1)
                if CF == 1 then jmp BB8 else jmp BB9
            ; succ: [BB9, BB8]

            ; pred: [BB4]
            BB8: ; [then]
                jmp BB5
            ; succ: [BB5]

            ; pred: [BB8, BB11]
            BB5: ; [loop update]
                j_v3 = j_v2 + 1
                %13_v1 = j_v3 < 10
                cmp(%13_v1, 1)
                if CF == 1 then jmp BB4 else jmp BB6
            ; succ: [BB4, BB6]

            ; pred: [BB10, BB5]
            BB6: ; [loop tail]
                jmp BB7
            ; succ: [BB7]

            ; pred: [BB4]
            BB9: ; [merge]
                %8_v1 = j_v2 == 7
                cmp(%8_v1, 1)
                if CF == 1 then jmp BB10 else jmp BB11
            ; succ: [BB11, BB10]

            ; pred: [BB9]
            BB10: ; [then]
                jmp BB6
            ; succ: [BB6]

            ; pred: [BB9]
            BB11: ; [merge]
                jmp BB5
            ; succ: [BB5]
        """).strip()

        self.assert_ir(src, expected_ir)

    def test_for_loop_var_init_assign(self):
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

    def test_uncond_loop_gen(self):
        src = self.make_main("""
            let i int = 0;
            for {
                if (i == 5) {
                    continue;
                }

                if (i > 10) {
                    break;
                }
            }
            return 0;
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                i_v1 = 0
                jmp BB2
            ; succ: [BB2]

            ; pred: [BB0]
            BB2: ; [uncond loop preheader]
                jmp BB3
            ; succ: [BB3]

            ; pred: [BB2, BB4]
            BB3: ; [uncond loop header]
                %0_v1 = i_v1 == 5
                cmp(%0_v1, 1)
                if CF == 1 then jmp BB7 else jmp BB8
            ; succ: [BB8, BB7]

            ; pred: [BB3]
            BB7: ; [then]
                jmp BB4
            ; succ: [BB4]

            ; pred: [BB7, BB10]
            BB4: ; [uncond loop update]
                jmp BB3
            ; succ: [BB3]

            ; pred: [BB3]
            BB8: ; [merge]
                %3_v1 = i_v1 > 10
                cmp(%3_v1, 1)
                if CF == 1 then jmp BB9 else jmp BB10
            ; succ: [BB10, BB9]

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

            ; pred: [BB8]
            BB10: ; [merge]
                jmp BB4
            ; succ: [BB4]
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
                (A_v1<~)%5_v1 = (<~)A_v1 + %4_v1
                Store((A_v1<~)%5_v1, 10)
                jmp BB5
            ; succ: [BB5]

            ; pred: [BB4]
            BB5: ; [loop update]
                i_v3 = i_v2 + 1
                %9_v1 = i_v3 < 64
                cmp(%9_v1, 1)
                if CF == 1 then jmp BB4 else jmp BB6
            ; succ: [BB4, BB6]

            ; pred: [BB5]
            BB6: ; [loop tail]
                jmp BB7
            ; succ: [BB7]
        """).strip()

        self.assert_ir(src, expected_ir)
