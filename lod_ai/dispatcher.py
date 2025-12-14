"""
Tiny message router used by Engine.

    disp = Dispatcher()
    disp.register_cmd("march", march.execute)
    disp.register_sa ("partisans", sa_partisans.execute)

    disp.execute("march", faction="BRITISH", space="Boston")
"""

from typing import Callable, Dict, Any


class Dispatcher:
    """Map op-strings to callables and execute them with kw-params."""

    def __init__(self) -> None:
        self._cmd: Dict[str, Callable[..., Any]] = {}
        self._sa:  Dict[str, Callable[..., Any]] = {}

    # ------------- registration helpers -----------------
    def register_cmd(self, label: str, func: Callable[..., Any]) -> None:
        if label in self._cmd:
            raise ValueError(f"Command '{label}' already registered")
        self._cmd[label] = func

    def register_sa(self, label: str, func: Callable[..., Any]) -> None:
        if label in self._sa:
            raise ValueError(f"SA '{label}' already registered")
        self._sa[label] = func

    # ------------- runtime dispatch ---------------------
    def execute(self, label: str, *, faction: str, space: str | None = None,
                free: bool = False, **kwargs) -> Any:
        """
        • label   – op-string exactly as registered
        • faction – acting faction
        • space   – single space id or None (most Commands want it)
        • free    – True if this is a card-granted free action
        • kwargs  – any extra options (option=2, etc.)

        Decides whether it is a Command or SA based on which table holds the label.
        """
        if label in self._cmd:
            return self._cmd[label](faction=faction, space_id=space,
                                    free=free, **kwargs)
        if label in self._sa:
            return self._sa[label](faction=faction, space_id=space,
                                   free=free, **kwargs)
        raise KeyError(f"Action label '{label}' not registered")
