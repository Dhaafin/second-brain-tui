from textual.widgets import DirectoryTree
from textual.containers import Vertical

class SidebarPanel(Vertical):
    def compose(self):
        yield DirectoryTree(path=self.app.agent.vault_path, id="file-tree")
