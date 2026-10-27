import sys
from typing import List, Union, Any, Optional
from prompt_toolkit import Application, HTML
from prompt_toolkit.layout import Layout, Window, HSplit
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.shortcuts import PromptSession
from prompt_toolkit.data_structures import Point


class _MenuState:
    def __init__(self, choices, shortcuts, selected=0):
        self.choices = choices
        self.shortcuts = shortcuts
        self.selected = selected


def _get_choice_text_and_value(choice):
    if isinstance(choice, str):
        return choice, choice
    if hasattr(choice, "title"):
        title = choice.title
    elif hasattr(choice, "text"):
        title = choice.text
    else:
        title = str(choice)
    if hasattr(choice, "value"):
        value = choice.value
    else:
        value = title
    return title, value


async def menu_select(
    message: str,
    choices: List[Union[str, Any]],
    shortcuts: Optional[List[str]] = None,
    descriptions: Optional[List[str]] = None,
    settings_line: bool = False,
    page_nav: Optional[dict] = None,
) -> str:
    """Display a menu with letter/character shortcuts.

    Keys:
        j / Down     : navigate down
        k / Up       : navigate up
        l / Enter    : select current item
        h            : return "__back__"
        q            : exit program
        shortcut key : select item directly
        n / p        : page next / prev (when page_nav enabled)
        .            : return "__settings__" (if settings_line is set)
    """
    parsed = [_get_choice_text_and_value(c) for c in choices]

    if shortcuts is None:
        shortcuts = []
    shortcuts = shortcuts + [""] * (len(parsed) - len(shortcuts))

    if descriptions is None:
        descriptions = []
    descriptions = descriptions + [""] * (len(parsed) - len(descriptions))

    state = _MenuState(parsed, shortcuts, 0)

    kb = KeyBindings()

    @kb.add("q")
    def _(event):
        event.app.exit(result="__quit__")

    @kb.add("h")
    @kb.add("left")
    def _(event):
        event.app.exit(result="__back__")

    @kb.add("j")
    @kb.add("down")
    def _(event):
        if len(state.choices) > 0:
            state.selected = (state.selected + 1) % len(state.choices)

    @kb.add("k")
    @kb.add("up")
    def _(event):
        if len(state.choices) > 0:
            state.selected = (state.selected - 1) % len(state.choices)

    @kb.add("l")
    @kb.add("right")
    @kb.add("enter")
    def _(event):
        if len(state.choices) > 0:
            _, value = state.choices[state.selected]
            event.app.exit(result=value)

    # Build protected key set dynamically based on active features
    protected = {"h", "j", "k", "l", "q"}
    if page_nav:
        protected.update({"n", "p"})
    if settings_line:
        protected.add(".")

    for i, sc in enumerate(state.shortcuts):
        if not sc or sc in protected:
            continue

        def make_handler(idx):
            def handler(event):
                if 0 <= idx < len(state.choices):
                    _, value = state.choices[idx]
                    event.app.exit(result=value)
            return handler

        kb.add(sc)(make_handler(i))

    if page_nav and page_nav.get("has_prev"):
        @kb.add("p")
        def _(event):
            event.app.exit(result="__prev__")

    if page_nav and page_nav.get("has_next"):
        @kb.add("n")
        def _(event):
            event.app.exit(result="__next__")

    if settings_line:
        @kb.add(".")
        def _(event):
            event.app.exit(result="__settings__")

    def get_formatted_text():
        lines = [("class:msg", f"{message}\n\n")]
        for i, (text, _) in enumerate(state.choices):
            sc = state.shortcuts[i]
            desc = descriptions[i]
            prefix = f"[{sc}] " if sc else ""
            if i == state.selected:
                lines.append(("class:pointer", f"> {prefix}{text}\n"))
            else:
                lines.append(("", f"  {prefix}{text}\n"))
            if desc:
                lines.append(("class:hint", f"      {desc}\n"))

        # Page navigation line
        if page_nav:
            has_prev = page_nav.get("has_prev")
            has_next = page_nav.get("has_next")
            if has_prev or has_next:
                prev_part = "[p] Previous Page" if has_prev else " " * len("[p] Previous Page")
                next_part = "[n] Next Page" if has_next else ""
                parts = [prev_part, next_part] if next_part else [prev_part]
                lines.append(("", "\n" + "      ".join(parts) + "\n"))

        lines.append(("class:hint", "\n[h] Back   [↑k] Up     [l/⏎] Select\n"))
        if settings_line:
            lines.append(("class:hint", "[q] Quit   [↓j] Down   [.] Settings"))
        else:
            lines.append(("class:hint", "[q] Quit   [↓j] Down"))
        return lines

    def _cursor_position():
        # Visual line of the selected choice: title (line 0) + blank (line 1) + choice offset
        return Point(0, 2 + state.selected)

    control = FormattedTextControl(
        get_formatted_text,
        focusable=True,
        show_cursor=False,
        get_cursor_position=_cursor_position,
    )

    root_container = HSplit([
        Window(content=control, height=Dimension()),
    ])

    app = Application(
        layout=Layout(root_container),
        key_bindings=kb,
        full_screen=True,
        mouse_support=False,
    )

    result = await app.run_async()

    if result == "__quit__":
        print("\nExiting...")
        sys.exit(0)

    return result


_TOOLBAR_HTML = HTML('<style fg="#6c6c6c">[Ctrl+C] Cancel</style>')


def _cancel_toolbar():
    return _TOOLBAR_HTML


async def ask_text(message: str, password: bool = False) -> Optional[str]:
    """Prompt for text input with a [Ctrl+C] Cancel hint. Returns None on cancel."""
    session = PromptSession(bottom_toolbar=_cancel_toolbar)
    try:
        result = await session.prompt_async(message, is_password=password)
        return result if result else None
    except (KeyboardInterrupt, EOFError):
        return None


async def ask_confirm(message: str) -> Optional[bool]:
    """Prompt for yes/no confirmation with a [Ctrl+C] Cancel hint. Returns None on cancel."""
    session = PromptSession(bottom_toolbar=_cancel_toolbar)
    try:
        raw = (await session.prompt_async(message + " (y/n): ")).strip().lower()
        return raw in ("y", "yes")
    except (KeyboardInterrupt, EOFError):
        return None
