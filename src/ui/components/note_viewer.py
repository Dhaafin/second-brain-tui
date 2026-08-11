"""Note Viewer Panel — Displays selected note content with close button."""

from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Label

from src.ui.components.chat_panel import FocusableMarkdown


class NoteViewerPanel(Vertical):
    """Panel for reading note files selected from the sidebar."""

    def compose(self):
        with Horizontal(id="note-viewer-header"):
            yield Label("📄 Note Viewer", id="note-viewer-title")
            yield Button("✕", id="close-note-btn", variant="error")
        yield FocusableMarkdown(
            "# Select a Note\n\nPlease select a note from the left sidebar to read it here...",
            id="note-viewer",
        )
