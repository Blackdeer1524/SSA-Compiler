import textwrap

from src.optimizations.dce import DCE
from src.optimizations.sccp import SCCP
from tests import base


class TestSCCPAndDCE(base.TestBase):
    def __init__(self, *args):
        passes = [SCCP, DCE]
        super().__init__(passes, *args)

    def test_dead_on_condition(self):
        src = self.make_main("""
            let a int = 0; // dead
            let N int = 0;
            if (N == 0) {
                return N;
            }
            // dead code
            a = N + 10;
            return a;
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                jmp BB2
            ; succ: [BB2]

            ; pred: [BB0]
            BB2: ; [then]
                return(0)
            ; succ: [BB1]

            ; pred: [BB2]
            BB1: ; [exit]
            ; succ: []
        """).strip()

        self.assert_ir(src, expected_ir)

    def test_dead_loop_causes_dead_code(self):
        src = self.make_main("""
            let N int = 0;
            let a int = 0;
            let c int = 0;
            for (let i int = 0; i < N; i = i + 1) {
                a = (a + 1) * 2;
            }
            return c;
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                jmp BB2
            ; succ: [BB2]

            ; pred: [BB0]
            BB2: ; [condition check]
                jmp BB7
            ; succ: [BB7]

            ; pred: [BB2]
            BB7: ; [loop exit]
                return(0)
            ; succ: [BB1]

            ; pred: [BB7]
            BB1: ; [exit]
            ; succ: []
        """).strip()

        self.assert_ir(src, expected_ir)

