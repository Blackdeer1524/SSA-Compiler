from src.ssa.cfg import CFG, BasicBlock, InstUncondJump


class BlockCleanup:
    def run(self, cfg: CFG):
        changed = True
        while changed:
            changed = False
            # Materialize list because we mutate the CFG while iterating.
            for bb in cfg:
                if self._is_trivial_jump_block(cfg, bb):
                    self._remove_block(bb)
                    changed = True
                    break

    def _is_trivial_jump_block(self, cfg: CFG, bb: BasicBlock) -> bool:
        if bb is cfg.entry or bb is cfg.exit:
            return False
        if len(bb.instructions) != 1:
            return False
        if bb.phi_nodes:
            return False
        inst = bb.instructions[0]
        if not isinstance(inst, InstUncondJump):
            return False
        if len(bb.preds) != 1 or len(bb.succ) != 1:
            return False
        if len(bb.preds[0].succ) != 1:
            return False

        pred = bb.preds[0]
        succ = bb.succ[0]

        if pred is bb or succ is bb:
            return False

        return True

    def _remove_block(self, bb: BasicBlock):
        pred = bb.preds[0]
        succ = bb.succ[0]

        # Update PHI nodes on the successor to point to the predecessor.
        for phi in succ.phi_nodes.values():
            if bb.label in phi.rhs:
                incoming_val = phi.rhs.pop(bb.label)
                # Do not overwrite an existing entry for the predecessor.
                if pred.label not in phi.rhs:
                    phi.rhs[pred.label] = incoming_val

        if bb in pred.succ:
            pred.succ.remove(bb)
        if bb in succ.preds:
            succ.preds.remove(bb)

        pred.add_child(succ)

        bb.preds.clear()
        bb.succ.clear()

