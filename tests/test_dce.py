import textwrap

from src.optimizations.dce import DCE
from tests import base


class TestDCE(base.TestBase):
    def __init__(self, *args):
        passes = [DCE]
        super().__init__(passes, *args)

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
