from textual.containers import Vertical
from textual.widgets import Button, DirectoryTree
from rich.text import Text


class AestheticDirectoryTree(DirectoryTree):
    """DirectoryTree with custom emojis for folders and file types."""

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
            # Custom folder icon based on expansion state
            icon = "📂 " if node.is_expanded else "📁 "
            node_label.stylize_before(self.get_component_rich_style("directory-tree--folder", partial=True))
            prefix = (icon, base_style)
        else:
            # Custom icon based on file extension
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


class SidebarPanel(Vertical):
    """Sidebar panel containing the custom file explorer and settings button."""

    def compose(self):
        yield AestheticDirectoryTree(path=self.app.agent.vault_path, id="file-tree")
        yield Button("⚙ Settings", id="sidebar-settings-btn")
