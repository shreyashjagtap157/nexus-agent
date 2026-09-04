import sys

class ImportBlocker:
    def __init__(self, *module_names: str) -> None:
        self.module_names = module_names

    def find_spec(self, fullname: str, path: str | None, target: str | None = None) -> None:
        if fullname in self.module_names:
            raise ImportError(f"No module named '{fullname}'")
        return None
