from textual.containers import Vertical
from textual.widgets import DirectoryTree


class SidebarPanel(Vertical):
    def compose(self):
        yield DirectoryTree(path=self.app.agent.vault_path, id="file-tree")
