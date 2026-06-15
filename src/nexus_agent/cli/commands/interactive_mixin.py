"""Interactive UI helpers — menus, model config HUD, provider connection.

Extracted from the monolithic command_dispatcher.py to reduce file size.
Interactive UI primitives now live in ``InteractiveUIMixin`` in
``interactive_ui.py``; this module retains only the thin public
mixin that ``CommandDispatcherMixin`` inherits.
"""

from __future__ import annotations

from nexus_agent.cli.commands.interactive_ui import InteractiveUIMixin


class InteractiveCommandsMixin(InteractiveUIMixin):
    """Mixin providing interactive UI helpers: menus, model config HUD, provider connect.

    All interactive UI primitives are inherited from ``InteractiveUIMixin``
    (``interactive_ui.py``).  This class exists solely to maintain the
    ``InteractiveCommandsMixin`` name in ``CommandDispatcherMixin``'s MRO.
    """
