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

    def __init__(self, engine: Any | None = None) -> None:
        self.engine = engine
        self._cmd: Dict[str, Callable[..., Any]] = {}
        self._sa:  Dict[str, Callable[..., Any]] = {}
        self.human_factions = set()
        self._last_action: Dict[str, str | None] = {}

    def set_human_factions(self, factions) -> None:
        """Set the factions that are human-controlled for this game."""
        self.human_factions = set(factions)

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

    # --------- helpers for interactive CLI support -------------------
    def execute_event(self, faction: str, card: Any) -> Any:
        """Process a faction playing the event on the given card."""
        self._last_action[faction] = "event"
        if self.engine and hasattr(self.engine, "handle_event"):
            return self.engine.handle_event(faction, card)
        return None

    def execute_command(self, faction: str, command: str, special: str | None = None,
                        limited: bool = False) -> Any:
        """Execute a command (with optional special) for the given faction."""
        self._last_action[faction] = "command"
        if self.engine and hasattr(self.engine, "dispatcher"):
            return self.engine.dispatcher.execute(
                command, faction=faction, space=None, limited=limited, special=special
            )
        return None

    def execute_bot_turn(self, faction: str, card: Any, first_action: str | None = None) -> Any:
        """Execute a bot turn for the provided faction."""
        if faction in self.human_factions:
            return None
        self._last_action[faction] = None
        if self.engine and hasattr(self.engine, "bots"):
            bot = self.engine.bots.get(faction)
            if bot:
                bot.take_turn(self.engine.state, card)
                self._last_action[faction] = getattr(self.engine, "last_action", lambda f: None)(faction)
        return self._last_action.get(faction)

    def last_action(self, faction: str) -> str | None:
        """Return the last recorded action for the faction."""
        return self._last_action.get(faction)
