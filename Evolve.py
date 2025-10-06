from abc import ABC, abstractmethod
from typing import List, Tuple

class EvolveInterface(ABC):
    @abstractmethod
    def initial_prompt(self) -> str:
        pass

    @abstractmethod
    def mutate_prompt(self, versions: List[str]) -> str:
        pass

    @abstractmethod
    def debug_prompt(self, stdout, stderr) -> str:
        pass

    @abstractmethod
    def build(self, code: str) -> Tuple[bool, str, str]:
        """
        Returns (success, stdout, stderr)
        """
        pass
    
    @abstractmethod
    def run_experiment(self):
        """
        Returns two dictionaries: eval_results, eval_logs
        """
        pass
    
    @abstractmethod
    def run_info(self) -> str:
        pass