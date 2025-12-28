from abc import ABC, abstractmethod

from src.ir.cfg import CFG


class OptimizationPass(ABC):
    @abstractmethod
    def run(self, cfg: CFG): ...
