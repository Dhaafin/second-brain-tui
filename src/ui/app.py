import os
from dotenv import load_dotenv
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DirectoryTree, Footer, Header, Input, Label, Markdown

from src.agent import SecondBrainAgent
from src.ui.components.sidebar import SidebarPanel
from src.ui.components.note_viewer import NoteViewerPanel
from src.ui.components.chat_panel import ChatPanel

load_dotenv(".env.local")

class SecondBrainApp(App):
    """Aplikasi TUI Utama dengan Layout & Interaksi Dasar."""

    CSS_PATH = "../../app.tcss"

    BINDINGS = (
        ("q", "quit", "Quit"),
        ("c", "clear_chat", "Clear Chat"),
        ("escape", "close_viewer", "Close Note / Cancel Agent"),
    )

    def __init__(self) -> None:
        super().__init__()
        self.agent = SecondBrainAgent()

    def on_mount(self) -> None:
        # Sembunyikan container pembaca catatan di awal
        self.query_one("#note-viewer-container").display = False

        # Check if Agent Memory.md exists in the vault
        memory_file_path = os.path.join(self.agent.vault_path, "Agent Memory.md")
        if not os.path.exists(memory_file_path):
            self.agent.awaiting_onboarding_consent = True
            chat_panel = self.query_one(ChatPanel)
            chat_panel.chat_history.append(
                "### Agent\n"
                "Hi! I noticed that you don't have an `Agent Memory.md` file in your vault. "
                "This file helps me remember your preferences (like project directories, logging rules, etc.) "
                "across sessions. Do you want me to initialize it for you? (Type **yes** or **no**)"
            )
            chat_log = chat_panel.query_one("#chat-log", Markdown)
            chat_log.update("\n\n".join(chat_panel.chat_history))

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        """Handler ketika file di-klik di sidebar explorer."""
        file_path = event.path
        if file_path.suffix.lower() in (".md", ".txt", ".json", ".py", ".tcss", ".env", ".local"):
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                note_viewer = self.query_one("#note-viewer", Markdown)
                note_viewer.update(content)
                self.query_one("#note-viewer-title", Label).update(f"📄 {file_path.name}")
                self.query_one("#note-viewer-container").display = True
            except OSError:
                pass

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal():
            yield SidebarPanel(id="sidebar")

            with Vertical(id="main-content"):
                yield NoteViewerPanel(id="note-viewer-container")
                yield ChatPanel(id="chat-area")

        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handler ketika tombol X diklik untuk menutup note viewer."""
        if event.button.id == "close-note-btn":
            self.action_close_viewer()

    def action_clear_chat(self) -> None:
        """Aksi ketika menekan tombol 'c' untuk membersihkan log chat."""
        chat_panel = self.query_one(ChatPanel)
        chat_panel.chat_history = []
        self.agent.clear_history()
        chat_panel.query_one("#chat-log", Markdown).update("")

    def action_close_viewer(self) -> None:
        """Sembunyikan panel pembaca catatan ATAU batalkan pencarian Agent jika sedang berjalan."""
        chat_panel = self.query_one(ChatPanel)
        if hasattr(chat_panel, "current_worker") and chat_panel.current_worker.is_running:
            chat_panel.current_worker.cancel()

            if hasattr(chat_panel, "loading_timer"):
                chat_panel.loading_timer.stop()
            
            loading_status = chat_panel.query_one("#loading-status", Label)
            loading_status.display = False

            chat_input = chat_panel.query_one("#chat-input", Input)
            chat_input.disabled = False
            chat_input.focus()

            chat_panel.chat_history.append("### Agent\n*(X) Search cancelled by user (Agnes fell off her surfboard 🏄💥...)*")
            
            chat_log = chat_panel.query_one("#chat-log", Markdown)
            chat_log.update("\n\n".join(chat_panel.chat_history))
            chat_panel.scroll_chat_to_bottom(chat_log)
        else:
            self.query_one("#note-viewer-container").display = False

if __name__ == "__main__":
    app = SecondBrainApp()
    app.run()
