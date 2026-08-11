"""Second Brain TUI — Main Application Entry Point."""

import asyncio
import os

from dotenv import load_dotenv
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DirectoryTree, Footer, Header, Input, Label, Markdown

from src.agent import SecondBrainAgent
from src.ui.components.chat_panel import ChatPanel
from src.ui.components.note_viewer import NoteViewerPanel
from src.ui.components.sidebar import SidebarPanel
from src.ui.components.settings_modal import SettingsModal

load_dotenv(".env.local")


class SecondBrainApp(App):
    """Main TUI Application with Catppuccin Mocha theme."""

    TITLE = "🧠 Second Brain TUI"
    SUB_TITLE = "v0.1 — Catppuccin Mocha"
    CSS_PATH = "../../app.tcss"

    BINDINGS = (
        ("q", "quit", "Quit"),
        ("c", "clear_chat", "Clear Chat"),
        ("escape", "close_viewer", "Close Note"),
        ("ctrl+c", "cancel_agent", "Cancel Agent"),
    )

    def __init__(self) -> None:
        super().__init__()
        self.agent = SecondBrainAgent()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal():
            yield SidebarPanel(id="sidebar")

            with Vertical(id="main-content"):
                yield NoteViewerPanel(id="note-viewer-container")
                yield ChatPanel(id="chat-area")

        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#note-viewer-container").display = False

        memory_file_path = os.path.join(self.agent.vault_path, "Agent Memory.md")
        if not os.path.exists(memory_file_path):
            self.agent.awaiting_onboarding_consent = True
            chat_panel = self.query_one(ChatPanel)
            chat_panel.mount_message(
                "Agent",
                "Hi! I noticed you don't have an `Agent Memory.md` file in your vault. "
                "This file helps me remember your preferences across sessions. "
                "Do you want me to initialize it for you? (Type **yes** or **no**)"
            )

        # Trigger background RAG sync
        self.run_worker(self._sync_rag_background())

    async def _sync_rag_background(self) -> None:
        """Incrementally sync vault files with Qdrant vector DB in the background."""
        from src.rag import sync_vault_embeddings

        chat_panel = self.query_one(ChatPanel)
        chat_panel.mount_message("Agent", "*🔄 Syncing your notes (RAG) in the background...*")

        try:
            await asyncio.to_thread(sync_vault_embeddings, self.agent.vault_path)
            chat_panel.mount_message("Agent", "*🟢 RAG sync complete! I now remember all your notes.*")
            chat_panel.update_rag_status()
        except Exception as e:
            chat_panel.mount_message("Agent", f"*⚠️ RAG sync failed: {e}*")

    # --- Event Handlers ---

    def on_directory_tree_file_selected(
        self, event: DirectoryTree.FileSelected
    ) -> None:
        """Open a file from the sidebar in the note viewer panel."""
        file_path = event.path
        if file_path.suffix.lower() in (".md", ".txt", ".json", ".py", ".tcss", ".env", ".local"):
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                self.query_one("#note-viewer", Markdown).update(content)
                self.query_one("#note-viewer-title", Label).update(f"📄 {file_path.name}")
                self.query_one("#note-viewer-container").display = True
            except OSError:
                pass

    def on_button_pressed(self, event) -> None:
        """Handle button clicks."""
        if event.button.id == "close-note-btn":
            self.action_close_viewer()
        elif event.button.id == "sidebar-settings-btn":
            self.action_open_settings()

    # --- Actions ---

    def action_open_settings(self) -> None:
        """Open the settings modal screen."""
        self.push_screen(SettingsModal(), callback=self.on_settings_closed)

    def on_settings_closed(self, preferences_updated: bool) -> None:
        """Callback triggered when the settings modal is closed."""
        if preferences_updated:
            self.agent.load_memory()
            self.notify("Settings saved successfully!", severity="information")

    def action_close_viewer(self) -> None:
        """Close the note viewer panel (Escape key)."""
        self.query_one("#note-viewer-container").display = False

    def action_cancel_agent(self) -> None:
        """Cancel a running AI request (Ctrl+C)."""
        chat_panel = self.query_one(ChatPanel)

        if not (hasattr(chat_panel, "current_worker") and chat_panel.current_worker.is_running):
            return

        chat_panel.current_worker.cancel()

        if hasattr(chat_panel, "loading_timer"):
            chat_panel.loading_timer.stop()

        loading_status = chat_panel.query_one("#loading-status", Label)
        loading_status.display = False

        chat_input = chat_panel.query_one("#chat-input")
        chat_input.disabled = False
        chat_input.focus()

        chat_panel.mount_message("Agent", "*(Request cancelled by user 🛑)*")

    def action_clear_chat(self) -> None:
        """Clear chat history and reset agent conversation."""
        chat_panel = self.query_one(ChatPanel)
        chat_panel.clear_chat_log()
        self.agent.clear_history()


if __name__ == "__main__":
    app = SecondBrainApp()
    app.run()
