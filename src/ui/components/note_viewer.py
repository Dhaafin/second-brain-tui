from textual.widgets import Button, Label, Markdown
from textual.containers import Horizontal, Vertical

class FocusableMarkdown(Markdown):
    """Markdown widget that can accept focus for keyboard scrolling."""
    can_focus = True

class NoteViewerPanel(Vertical):
    def compose(self):
        with Horizontal(id="note-viewer-header"):
            yield Label("📄 Note Viewer", id="note-viewer-title")
            yield Button("X", id="close-note-btn", variant="error")
        yield FocusableMarkdown(
            "# Select a Note\n\nPlease select a note from the left sidebar to read it here...",
            id="note-viewer"
        )
