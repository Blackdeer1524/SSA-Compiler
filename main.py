import argparse
from pprint import pprint
from src.parsing.lexer import Lexer
from src.parsing.parser import Parser
from src.parsing.semantic import SemanticAnalyzer
from src.ssa.cfg import CFGBuilder
from src.ssa.dominance import compute_dominance_frontier_graph, compute_dominator_tree
from src.ssa.ssa import SSABuilder
from src.optimizations.sccp import SCCP
from src.optimizations.licm import LICM
from src.optimizations.dce import DCE


def main():
    arg_parser = argparse.ArgumentParser(description="SSA-based optimizing compiler")
    arg_parser.add_argument(
        "-i",
        "--input",
        default="input.txt",
        help="Path to the source program to compile.",
    )
    arg_parser.add_argument(
        "--disable-licm",
        action="store_true",
        help="Skip Loop Invariant Code Motion optimization.",
    )
    arg_parser.add_argument(
        "--disable-sccp",
        action="store_true",
        help="Skip Sparse Conditional Constant Propagation optimization.",
    )
    arg_parser.add_argument(
        "--disable-dce",
        action="store_true",
        help="Skip Dead Code Elimination optimization.",
    )
    arg_parser.add_argument(
        "--disable-block-cleanup",
        action="store_true",
        help="Skip basic block cleanup pass.",
    )
    arg_parser.add_argument(
        "--dump-ir",
        metavar="PATH",
        help="Write the SSA IR to PATH after all passes run.",
    )
    arg_parser.add_argument(
        "--dump-cfg-dot",
        metavar="PATH",
        help="Write the CFG (with dominance info) to PATH in Graphviz .dot format.",
    )
    arg_parser.add_argument(
        "--disable-ssa",
        action="store_true",
        help="disables phi-nodes placement",
    )

    arg_parser.add_argument(
        "--disable-idom-tree",
        action="store_true",
        help="",
    )
    arg_parser.add_argument(
        "--disable-df",
        action="store_true",
        help="",
    )

    args = arg_parser.parse_args()

    with open(args.input, "r") as f:
        src = f.read()

    lexer = Lexer(src)
    parser = Parser(lexer)
    ast = parser.parse()
    analyzer = SemanticAnalyzer(ast)
    errors = analyzer.analyze()
    if len(errors) > 0:
        for err in errors:
            pprint(err)
        exit(1)

    builder = CFGBuilder()
    cfg = builder.build(ast)[0]

    if not args.disable_ssa:
        SSABuilder().build(cfg)
        if not args.disable_licm:
            LICM().run(cfg)
        if not args.disable_sccp:
            SCCP().run(cfg)
        if not args.disable_dce:
            DCE().run(cfg)
        # if not args.disable_block_cleanup:
        #     BlockCleanup().run(cfg)

    if args.dump_ir:
        ir = cfg.to_IR()
        with open(args.dump_ir, "w") as f:
            f.write(ir)
        print(ir)
    else:
        idom_tree = compute_dominator_tree(cfg)

        if args.disable_idom_tree:
            rev_idom = {}
        else:
            rev_idom = idom_tree.reversed_idom

        if args.disable_df:
            df = {}
        else:
            df = compute_dominance_frontier_graph(cfg, idom_tree)

        graphviz = cfg.to_graphviz(src, rev_idom, df)
        if args.dump_cfg_dot:
            with open(args.dump_cfg_dot, "w") as f:
                f.write(graphviz)
        else:
            print(graphviz)


if __name__ == "__main__":
    main()
