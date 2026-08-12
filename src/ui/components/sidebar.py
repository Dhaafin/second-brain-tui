"""Sidebar Panel — Custom directory explorer with right-click context menus and file management."""

import os
import shutil
from pathlib import Path

from rich.text import Text
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DirectoryTree, Input, Label, OptionList
from textual.widgets.option_list import Option


class ConfirmModal(ModalScreen[bool]):
    """Pop-up modal to confirm destructive operations (Yes/No)."""

    def __init__(self, message: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.message = message

    def compose(self):
        with Vertical(id="confirm-container"):
            yield Label(self.message, id="confirm-message")
            with Horizontal(id="confirm-buttons"):
                yield Button("Yes", variant="success", id="yes-btn")
                yield Button("No", id="no-btn")

    def on_mount(self) -> None:
        self.query_one("#confirm-container").border_title = "Confirm"
        self.query_one("#yes-btn").focus()

        # Entry animations
        self.styles.animate("background", "rgba(0, 0, 0, 0.6)", duration=0.25)
        container = self.query_one("#confirm-container")
        container.styles.animate("opacity", 1.0, duration=0.25, easing="out_cubic")
        container.styles.animate("offset", (0, 0), duration=0.25, easing="out_cubic")

    def dismiss_with_animation(self, result: bool) -> None:
        self.styles.animate("background", "rgba(0, 0, 0, 0.0)", duration=0.2)
        container = self.query_one("#confirm-container")
        container.styles.animate("opacity", 0.0, duration=0.2, easing="in_cubic")
        container.styles.animate("offset", (0, -10), duration=0.2, easing="in_cubic",
                                 on_complete=lambda: self.dismiss(result))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "yes-btn":
            self.dismiss_with_animation(True)
        else:
            self.dismiss_with_animation(False)


class PromptModal(ModalScreen[str]):
    """Pop-up modal to ask for a text input (e.g. renaming, new note name)."""

    def __init__(self, title: str, default_value: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self.title = title
        self.default_value = default_value

    def compose(self):
        with Vertical(id="prompt-container"):
            yield Label(self.title, id="prompt-title")
            yield Input(value=self.default_value, id="prompt-input")
            with Horizontal(id="prompt-buttons"):
                yield Button("Submit", variant="success", id="submit-btn")
                yield Button("Cancel", id="cancel-btn")

    def on_mount(self) -> None:
        self.query_one("#prompt-container").border_title = "Input"
        self.query_one("#prompt-input").focus()

        # Entry animations
        self.styles.animate("background", "rgba(0, 0, 0, 0.6)", duration=0.25)
        container = self.query_one("#prompt-container")
        container.styles.animate("opacity", 1.0, duration=0.25, easing="out_cubic")
        container.styles.animate("offset", (0, 0), duration=0.25, easing="out_cubic")

    def dismiss_with_animation(self, result: str) -> None:
        self.styles.animate("background", "rgba(0, 0, 0, 0.0)", duration=0.2)
        container = self.query_one("#prompt-container")
        container.styles.animate("opacity", 0.0, duration=0.2, easing="in_cubic")
        container.styles.animate("offset", (0, -10), duration=0.2, easing="in_cubic",
                                 on_complete=lambda: self.dismiss(result))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "submit-btn":
            self.dismiss_with_animation(self.query_one("#prompt-input").value)
        else:
            self.dismiss_with_animation("")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss_with_animation(event.value)


class ContextMenuModal(ModalScreen[str]):
    """Right-click drop-down context menu popup for files/folders."""

    def __init__(self, node_name: str, has_clipboard: bool, **kwargs) -> None:
        super().__init__(**kwargs)
        self.node_name = node_name
        self.has_clipboard = has_clipboard

    def compose(self):
        with Vertical(id="context-menu-container"):
            yield Label(f"📄 {self.node_name}", id="context-menu-title")

            options = [
                Option("📝 New Note", id="new"),
                Option("✏️ Rename", id="rename"),
                Option("📋 Copy", id="copy"),
                Option("✂️ Cut", id="cut"),
            ]
            if self.has_clipboard:
                options.append(Option("📥 Paste", id="paste"))
            options.append(Option("🗑️ Delete to Trash", id="delete"))

            yield OptionList(*options, id="context-menu-list")

    def on_mount(self) -> None:
        self.query_one("#context-menu-container").border_title = "Menu"
        self.query_one("#context-menu-list", OptionList).focus()

        # Entry animations
        self.styles.animate("background", "rgba(0, 0, 0, 0.6)", duration=0.25)
        container = self.query_one("#context-menu-container")
        container.styles.animate("opacity", 1.0, duration=0.25, easing="out_cubic")
        container.styles.animate("offset", (0, 0), duration=0.25, easing="out_cubic")

    def dismiss_with_animation(self, result: str) -> None:
        self.styles.animate("background", "rgba(0, 0, 0, 0.0)", duration=0.2)
        container = self.query_one("#context-menu-container")
        container.styles.animate("opacity", 0.0, duration=0.2, easing="in_cubic")
        container.styles.animate("offset", (0, -10), duration=0.2, easing="in_cubic",
                                 on_complete=lambda: self.dismiss(result))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss_with_animation(event.option.id)

    def on_key(self, event) -> None:
        if event.key == "escape":
            event.prevent_default()
            self.dismiss_with_animation("")


class AestheticDirectoryTree(DirectoryTree):
    """DirectoryTree with custom emojis and keyboard/mouse file manager actions."""

    BINDINGS = [
        ("c", "copy_file", "Copy"),
        ("x", "cut_file", "Cut"),
        ("v", "paste_file", "Paste"),
        ("delete", "delete_file", "Delete"),
        ("f2", "rename_file", "Rename"),
        ("n", "new_file", "New Note"),
    ]

    def render_label(self, node, base_style, style) -> Text:
        node_label = node._label.copy()
        node_label.stylize(style)

        if not self.is_mounted:
            return node_label

        dir_entry = node.data
        if dir_entry is None:
            return node_label

        path = dir_entry.path

        if path.is_dir():
            icon = "📂 " if node.is_expanded else "📁 "
            node_label.stylize_before(self.get_component_rich_style("directory-tree--folder", partial=True))
            prefix = (icon, base_style)
        else:
            suffix = path.suffix.lower()
            if suffix == ".md":
                icon = "📝 "
            elif suffix in (".py", ".pyw"):
                icon = "🐍 "
            elif suffix in (".json", ".yaml", ".yml", ".toml"):
                icon = "⚙️ "
            elif suffix in (".env", ".local"):
                icon = "🔑 "
            elif suffix in (".tcss", ".css"):
                icon = "🎨 "
            else:
                icon = "📄 "

            node_label.stylize_before(self.get_component_rich_style("directory-tree--file", partial=True))
            node_label.highlight_regex(
                r"\..+$",
                self.get_component_rich_style("directory-tree--extension", partial=True),
            )
            prefix = (icon, base_style)

        if node_label.plain.startswith("."):
            node_label.stylize_before(self.get_component_rich_style("directory-tree--hidden", partial=True))

        return Text.assemble(prefix, node_label)

    async def _on_mouse_down(self, event) -> None:
        """Capture right-clicks to show the custom context menu."""
        if event.button == 3:  # Right-click
            event.prevent_default()
            meta = event.style.meta
            if "line" in meta:
                cursor_line = meta["line"]
                node = self.get_node_at_line(cursor_line)
                if node is not None:
                    self.cursor_line = cursor_line
                    self.action_show_context_menu(node)
        else:
            await super()._on_mouse_down(event)

    # --- Context Menu Launcher ---

    def action_show_context_menu(self, node) -> None:
        """Display the context menu modal pop-up."""
        has_clipboard = getattr(self.app, "tui_clipboard", None) is not None
        self.app.push_screen(
            ContextMenuModal(node.data.path.name, has_clipboard),
            callback=lambda action: self._handle_context_menu_callback(action, node),
        )

    def _handle_context_menu_callback(self, action: str | None, node) -> None:
        if not action:
            return
        if action == "new":
            self.action_new_file()
        elif action == "rename":
            self.action_rename_file()
        elif action == "copy":
            self.action_copy_file()
        elif action == "cut":
            self.action_cut_file()
        elif action == "paste":
            self.action_paste_file()
        elif action == "delete":
            self.action_delete_file()

    # --- Keyboard Actions ---

    def action_copy_file(self) -> None:
        """Copy currently focused file path to TUI clipboard."""
        node = self.cursor_node
        if not node or not node.data:
            return
        self.app.tui_clipboard = {"path": node.data.path, "action": "copy"}
        self.app.notify(f"Copied: {node.data.path.name}")

    def action_cut_file(self) -> None:
        """Cut currently focused file path to TUI clipboard."""
        node = self.cursor_node
        if not node or not node.data:
            return
        self.app.tui_clipboard = {"path": node.data.path, "action": "cut"}
        self.app.notify(f"Cut: {node.data.path.name}")

    def action_paste_file(self) -> None:
        """Paste file from TUI clipboard into currently focused directory."""
        clipboard = getattr(self.app, "tui_clipboard", None)
        if not clipboard:
            self.app.notify("Clipboard is empty", severity="warning")
            return

        node = self.cursor_node
        if not node or not node.data:
            return

        target_dir = node.data.path if node.data.path.is_dir() else node.data.path.parent
        src_path = clipboard["path"]
        dest_path = target_dir / src_path.name

        if not src_path.exists():
            self.app.notify("Source file no longer exists", severity="error")
            self.app.tui_clipboard = None
            return

        if src_path == dest_path:
            self.app.notify("Source and destination are identical", severity="warning")
            return

        try:
            if clipboard["action"] == "copy":
                if src_path.is_dir():
                    shutil.copytree(src_path, dest_path)
                else:
                    shutil.copy2(src_path, dest_path)
                self.app.notify(f"Pasted copy of {src_path.name}")
            else:
                shutil.move(str(src_path), str(dest_path))
                # Update RAG
                rel_src = os.path.relpath(src_path, self.app.agent.vault_path)
                rel_dest = os.path.relpath(dest_path, self.app.agent.vault_path)
                from src.rag import delete_file_index, index_file
                delete_file_index(rel_src)
                index_file(self.app.agent.vault_path, rel_dest)

                self.app.tui_clipboard = None
                self.app.notify(f"Moved {src_path.name}")

            self.reload()
        except Exception as e:
            self.app.notify(f"Paste failed: {e}", severity="error")

    def action_delete_file(self) -> None:
        """Move the focused file or directory to trash after confirmation."""
        node = self.cursor_node
        if not node or not node.data:
            return
        path = node.data.path
        self.app.push_screen(
            ConfirmModal(f"Move '{path.name}' to trash?"),
            callback=lambda yes: self._handle_delete_callback(yes, path),
        )

    def _handle_delete_callback(self, yes: bool, path: Path) -> None:
        if not yes:
            return
        try:
            rel_path = os.path.relpath(path, self.app.agent.vault_path)
            from src.rag import delete_directory_index, delete_file_index
            from src.vault import delete_directory_to_trash, delete_to_trash

            if path.is_dir():
                res = delete_directory_to_trash(self.app.agent.vault_path, rel_path)
                if not res.startswith("Error"):
                    delete_directory_index(rel_path)
            else:
                res = delete_to_trash(self.app.agent.vault_path, rel_path)
                if not res.startswith("Error"):
                    delete_file_index(rel_path)

            if res.startswith("Error"):
                self.app.notify(res, severity="error")
            else:
                self.app.notify(f"Moved to trash: {path.name}")
                self.reload()
        except Exception as e:
            self.app.notify(f"Deletion failed: {e}", severity="error")

    def action_rename_file(self) -> None:
        """Rename the focused file or directory via text prompt."""
        node = self.cursor_node
        if not node or not node.data:
            return
        path = node.data.path
        self.app.push_screen(
            PromptModal(f"Rename '{path.name}' to:", default_value=path.name),
            callback=lambda new_name: self._handle_rename_callback(new_name, path),
        )

    def _handle_rename_callback(self, new_name: str | None, path: Path) -> None:
        if not new_name or new_name == path.name:
            return
        new_path = path.parent / new_name
        try:
            shutil.move(str(path), str(new_path))

            rel_old = os.path.relpath(path, self.app.agent.vault_path)
            rel_new = os.path.relpath(new_path, self.app.agent.vault_path)

            from src.rag import delete_directory_index, delete_file_index, index_file
            if path.is_dir():
                delete_directory_index(rel_old)
            else:
                delete_file_index(rel_old)
                index_file(self.app.agent.vault_path, rel_new)

            self.app.notify(f"Renamed to: {new_name}")
            self.reload()
        except Exception as e:
            self.app.notify(f"Rename failed: {e}", severity="error")

    def action_new_file(self) -> None:
        """Create a new markdown note inside the focused directory."""
        node = self.cursor_node
        if not node or not node.data:
            target_dir = Path(self.app.agent.vault_path)
        else:
            target_dir = node.data.path if node.data.path.is_dir() else node.data.path.parent

        self.app.push_screen(
            PromptModal("Create new note (.md):", default_value="Untitled.md"),
            callback=lambda note_name: self._handle_new_note_callback(note_name, target_dir),
        )

    def _handle_new_note_callback(self, note_name: str | None, target_dir: Path) -> None:
        if not note_name:
            return
        if not note_name.endswith(".md"):
            note_name += ".md"

        new_file_path = target_dir / note_name
        try:
            if new_file_path.exists():
                self.app.notify(f"File '{note_name}' already exists", severity="warning")
                return

            new_file_path.write_text("# " + note_name[:-3] + "\n", encoding="utf-8")

            rel_path = os.path.relpath(new_file_path, self.app.agent.vault_path)
            from src.rag import index_file
            index_file(self.app.agent.vault_path, rel_path)

            self.app.notify(f"Created note: {note_name}")
            self.reload()
        except Exception as e:
            self.app.notify(f"Failed to create note: {e}", severity="error")


class SidebarPanel(Vertical):
    """Sidebar panel containing the custom file explorer and settings button."""

    def compose(self):
        yield AestheticDirectoryTree(path=self.app.agent.vault_path, id="file-tree")
        yield Button("⚙ Settings", id="sidebar-settings-btn")
