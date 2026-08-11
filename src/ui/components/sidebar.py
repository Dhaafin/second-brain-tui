from textual.containers import Vertical
from textual.widgets import Button, DirectoryTree


class SidebarPanel(Vertical):
    """Sidebar panel containing the file explorer and settings button."""

    def compose(self):
        yield DirectoryTree(path=self.app.agent.vault_path, id="file-tree")
        yield Button("⚙ Settings", id="sidebar-settings-btn")
