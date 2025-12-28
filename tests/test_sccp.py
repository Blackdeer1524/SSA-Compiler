import textwrap

from src.optimizations.sccp import SCCP
from tests import base


class TestSCCP(base.TestBase):
    def __init__(self, *args):
        passes = [SCCP]
        super().__init__(passes, *args)

    def test_constant_prop(self):
        src = self.make_main("""
        let a int = 0;
        return a;
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                a_v1 = 0
                return(0)
            ; succ: [BB1]

            ; pred: [BB0]
            BB1: ; [exit]
            ; succ: []        
        """).strip()

        self.assert_ir(src, expected_ir)

    def test_transition_const(self):
        src = self.make_main("""
            let a int = 0;
            let b int = a + 10;
            return b;
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                a_v1 = 0
                b_v1 = 10
                return(10)
            ; succ: [BB1]
            
            ; pred: [BB0]
            BB1: ; [exit]
            ; succ: []
        """).strip()

        self.assert_ir(src, expected_ir)

    def test_zero_mult(self):
        src = """
        func main() -> int {
            let a int = input();
            let b int = 0;
            let c int = a * b;  // 0
            let d int = b * a;  // 0
            return c + d;  // 0
        }
        
        func input() -> int {
            return 0;
        }
        """

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                a_v1 = input()
                b_v1 = 0
                c_v1 = 0
                d_v1 = 0
                %4_v1 = 0
                return(0)
            ; succ: [BB1]

            ; pred: [BB0]
            BB1: ; [exit]
            ; succ: []
        """).strip()

        self.assert_ir(src, expected_ir)

    def test_simple_unreachable_block_drop(self):
        src = self.make_main("""
            let a int = 0;
            if (a > 0) {
                a = 10;
            }
            return a;
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                a_v1 = 0
                %0_v1 = 0
                jmp BB3
            ; succ: [BB3]

            ; pred: [BB0]
            BB3: ; [merge]
                a_v3 = ϕ(BB0: 0)

                return(0)
            ; succ: [BB1]

            ; pred: [BB3]
            BB1: ; [exit]
            ; succ: []
        """).strip()

        self.assert_ir(src, expected_ir)

    def test_interblock_propogation(self):
        src = self.make_main("""
            let a int = 5;
            let b int = 10;
            if (a == 5) {
                b = a + 10;  // b = 15
            }
            return b;  // return 15
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                a_v1 = 5
                b_v1 = 10
                %0_v1 = 1
                jmp BB2
            ; succ: [BB2]

            ; pred: [BB0]
            BB2: ; [then]
                b_v2 = 15
                jmp BB3
            ; succ: [BB3]

            ; pred: [BB2]
            BB3: ; [merge]
                b_v3 = ϕ(BB2: 15)

                return(15)
            ; succ: [BB1]

            ; pred: [BB3]
            BB1: ; [exit]
            ; succ: []
        """).strip()

        self.assert_ir(src, expected_ir)

    def test_array_sum(self):
        src = self.make_main("""
            let arr [10]int = {};
            let s int = 0;
            for (let i int = 0; i < 10; i = i + 1) {
                s = s + arr[i];
            }
            return s;
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                (<~)arr_v1 = array_init([10])
                s_v1 = 0
                jmp BB2
            ; succ: [BB2]

            ; pred: [BB0]
            BB2: ; [condition check]
                i_v1 = 0
                %0_v1 = 1
                jmp BB3
            ; succ: [BB3]

            ; pred: [BB2]
            BB3: ; [loop preheader]
                jmp BB4
            ; succ: [BB4]

            ; pred: [BB3, BB5]
            BB4: ; [loop body]
                s_v2 = ϕ(BB3: 0, BB5: s_v3)
                i_v2 = ϕ(BB3: 0, BB5: i_v3)

                %7_v1 = i_v2 * 1
                (arr_v1<~)%8_v1 = (<~)arr_v1 + %7_v1
                %4_v1 = Load((arr_v1<~)%8_v1)
                s_v3 = s_v2 + %4_v1
                jmp BB5
            ; succ: [BB5]

            ; pred: [BB4]
            BB5: ; [loop latch]
                i_v3 = i_v2 + 1
                %11_v1 = i_v3 < 10
                cmp(%11_v1, 0)
                if CF == 0 then jmp BB4 else jmp BB6
            ; succ: [BB4, BB6]

            ; pred: [BB5]
            BB6: ; [loop tail]
                jmp BB7
            ; succ: [BB7]

            ; pred: [BB6]
            BB7: ; [loop exit]
                s_v4 = ϕ(BB6: s_v3)

                return(s_v4)
            ; succ: [BB1]

            ; pred: [BB7]
            BB1: ; [exit]
            ; succ: []
        """).strip()

        self.assert_ir(src, expected_ir)

    def test_dead_cycle(self):
        src = self.make_main("""
            let N int = 0;
            for (let i int = 0; i < N; i = i + 1) { 
                N = (N + 1) * 2;
            }
            return N; // 0 
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                N_v1 = 0
                jmp BB2
            ; succ: [BB2]

            ; pred: [BB0]
            BB2: ; [condition check]
                i_v1 = 0
                %0_v1 = 0
                jmp BB7
            ; succ: [BB7]

            ; pred: [BB2]
            BB7: ; [loop exit]
                N_v4 = ϕ(BB2: 0)

                return(0)
            ; succ: [BB1]
            
            ; pred: [BB7]
            BB1: ; [exit]
            ; succ: []
        """).strip()
        self.assert_ir(src, expected_ir)

    def test_initially_dead_condition(self):
        src = self.make_main("""
            let N int = 0;
            for (let i int = 0; i < 10; i = i + 1) {
                if (N > 10) { // is initially considered as unreachable
                    break;  
                }
                N = (N + 1) * 2;
            }
            return N;
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                N_v1 = 0
                jmp BB2
            ; succ: [BB2]

            ; pred: [BB0]
            BB2: ; [condition check]
                i_v1 = 0
                %0_v1 = 1
                jmp BB3
            ; succ: [BB3]

            ; pred: [BB2]
            BB3: ; [loop preheader]
                jmp BB4
            ; succ: [BB4]

            ; pred: [BB3, BB5]
            BB4: ; [loop body]
                N_v2 = ϕ(BB3: 0, BB5: N_v4)
                i_v2 = ϕ(BB3: 0, BB5: i_v3)

                %3_v1 = N_v2 > 10
                cmp(%3_v1, 0)
                if CF == 0 then jmp BB8 else jmp BB9
            ; succ: [BB8, BB9]

            ; pred: [BB4]
            BB9: ; [merge]
                %6_v1 = N_v2 + 1
                N_v4 = %6_v1 * 2
                jmp BB5
            ; succ: [BB5]

            ; pred: [BB9]
            BB5: ; [loop latch]
                i_v3 = i_v2 + 1
                %12_v1 = i_v3 < 10
                cmp(%12_v1, 0)
                if CF == 0 then jmp BB4 else jmp BB6
            ; succ: [BB4, BB6]

            ; pred: [BB8, BB5]
            BB6: ; [loop tail]
                N_v3 = ϕ(BB8: N_v2, BB5: N_v4)

                jmp BB7
            ; succ: [BB7]

            ; pred: [BB6]
            BB7: ; [loop exit]
                N_v5 = ϕ(BB6: N_v3)

                return(N_v5)
            ; succ: [BB1]

            ; pred: [BB7]
            BB1: ; [exit]
            ; succ: []

            ; pred: [BB4]
            BB8: ; [then]
                jmp BB6
            ; succ: [BB6] 
        """).strip()

        self.assert_ir(src, expected_ir)

    def test_break_on_first_iter(self):
        src = self.make_main("""
            let N int = 5;
            for (let i int = 0; i < 10; i = i + 1) {
                if (N < 10) { 
                    break;
                }
                N = (N + 1) * 2;
            }
            return N;
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                N_v1 = 5
                jmp BB2
            ; succ: [BB2]

            ; pred: [BB0]
            BB2: ; [condition check]
                i_v1 = 0
                %0_v1 = 1
                jmp BB3
            ; succ: [BB3]

            ; pred: [BB2]
            BB3: ; [loop preheader]
                jmp BB4
            ; succ: [BB4]

            ; pred: [BB3]
            BB4: ; [loop body]
                N_v2 = ϕ(BB3: 5)
                i_v2 = ϕ(BB3: 0)

                %3_v1 = 1
                jmp BB8
            ; succ: [BB8]

            ; pred: [BB4]
            BB8: ; [then]
                jmp BB6
            ; succ: [BB6]

            ; pred: [BB8]
            BB6: ; [loop tail]
                N_v3 = ϕ(BB8: 5)

                jmp BB7
            ; succ: [BB7]

            ; pred: [BB6]
            BB7: ; [loop exit]
                N_v5 = ϕ(BB6: 5)

                return(5)
            ; succ: [BB1]

            ; pred: [BB7]
            BB1: ; [exit]
            ; succ: []
        """).strip()
        self.assert_ir(src, expected_ir)

    def test_complicacted_induction_doesnt_break_sccp(self):
        src = self.make_main("""
            let n int = 0;
            for (let i int = 0; i < 10; i = 2 * i + 1) {
                n = n + i;
            }
            return n;
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                n_v1 = 0
                jmp BB2
            ; succ: [BB2]

            ; pred: [BB0]
            BB2: ; [condition check]
                i_v1 = 0
                %0_v1 = 1
                jmp BB3
            ; succ: [BB3]

            ; pred: [BB2]
            BB3: ; [loop preheader]
                jmp BB4
            ; succ: [BB4]

            ; pred: [BB3, BB5]
            BB4: ; [loop body]
                n_v2 = ϕ(BB3: 0, BB5: n_v3)
                i_v2 = ϕ(BB3: 0, BB5: i_v3)

                n_v3 = n_v2 + i_v2
                jmp BB5
            ; succ: [BB5]

            ; pred: [BB4]
            BB5: ; [loop latch]
                %5_v1 = 2 * i_v2
                i_v3 = %5_v1 + 1
                %9_v1 = i_v3 < 10
                cmp(%9_v1, 0)
                if CF == 0 then jmp BB4 else jmp BB6
            ; succ: [BB4, BB6]

            ; pred: [BB5]
            BB6: ; [loop tail]
                jmp BB7
            ; succ: [BB7]

            ; pred: [BB6]
            BB7: ; [loop exit]
                n_v4 = ϕ(BB6: n_v3)

                return(n_v4)
            ; succ: [BB1]

            ; pred: [BB7]
            BB1: ; [exit]
            ; succ: [] 
        """).strip()

        self.assert_ir(src, expected_ir)

    def test_empty_cycle(self):
        src = self.make_main("""
          let N int = 5;
          let a int = 0;
          for (let i int = 0; i < 10; i = i + 1) {
              if (a != 0) {
                  N = N + 1;
                  break;
              }
          }
          return N;  // 5
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                N_v1 = 5
                a_v1 = 0
                jmp BB2
            ; succ: [BB2]

            ; pred: [BB0]
            BB2: ; [condition check]
                i_v1 = 0
                %0_v1 = 1
                jmp BB3
            ; succ: [BB3]

            ; pred: [BB2]
            BB3: ; [loop preheader]
                jmp BB4
            ; succ: [BB4]

            ; pred: [BB3, BB5]
            BB4: ; [loop body]
                i_v2 = ϕ(BB3: 0, BB5: i_v3)

                %3_v1 = 0
                jmp BB9
            ; succ: [BB9]

            ; pred: [BB4]
            BB9: ; [merge]
                jmp BB5
            ; succ: [BB5]

            ; pred: [BB9]
            BB5: ; [loop latch]
                i_v3 = i_v2 + 1
                %10_v1 = i_v3 < 10
                cmp(%10_v1, 0)
                if CF == 0 then jmp BB4 else jmp BB6
            ; succ: [BB4, BB6]

            ; pred: [BB5]
            BB6: ; [loop tail]
                N_v2 = ϕ(BB5: 5)

                jmp BB7
            ; succ: [BB7]

            ; pred: [BB6]
            BB7: ; [loop exit]
                N_v4 = ϕ(BB6: 5)

                return(5)
            ; succ: [BB1]

            ; pred: [BB7]
            BB1: ; [exit]
            ; succ: []
        """).strip()

        self.assert_ir(src, expected_ir)

    def test_unconditional_loop(self):
        src = self.make_main("""
            let N int = 0;
            for {
                let a int = N + 1;
                if (a == 1) {
                    break;
                }
                
                let unreachable int = 12 * a;
            }
            return N;
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                N_v1 = 0
                jmp BB2
            ; succ: [BB2]

            ; pred: [BB0]
            BB2: ; [uncond loop preheader]
                jmp BB3
            ; succ: [BB3]

            ; pred: [BB2]
            BB3: ; [uncond loop body]
                a_v1 = 1
                %2_v1 = 1
                jmp BB7
            ; succ: [BB7]

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

    def test_unary_ops(self):
        src = self.make_main("""
            let a int = 1 + (-2) - +3 + +10;
            if (!(a >= 11)) {
                return 12;
            }
            return 0;
        """)

        expected_ir = textwrap.dedent("""
            ; pred: []
            BB0: ; [entry]
                %3_v1 = -2
                %1_v1 = -1
                %5_v1 = 3
                %0_v1 = -4
                %7_v1 = 10
                a_v1 = 6
                %10_v1 = 0
                %9_v1 = 1
                jmp BB2
            ; succ: [BB2]
            
            ; pred: [BB0]
            BB2: ; [then]
                return(12)
            ; succ: [BB1]
            
            ; pred: [BB2]
            BB1: ; [exit]
            ; succ: []
        """).strip()

        self.assert_ir(src, expected_ir)