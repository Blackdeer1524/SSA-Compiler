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
            a int = 0; // dead
            N int = 0;
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
            ; succ: []
        """).strip()

        self.assert_ir(src, expected_ir)

    def test_dead_loop_causes_dead_code(self):
        src = self.make_main("""
            N int = 0;
            a int = 0;
            c int = 0;
            for (i int = 0; i < N; i = i + 1) {
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
            BB2: ; [loop init]
                jmp BB3
            ; succ: [BB3]

            ; pred: [BB2]
            BB3: ; [loop header]
                jmp BB4
            ; succ: [BB4]

            ; pred: [BB3]
            BB4: ; [loop exit]
                return(0)
            ; succ: []
        """).strip()

        self.assert_ir(src, expected_ir)
