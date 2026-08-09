import os
from dotenv import load_dotenv
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DirectoryTree, Footer, Header, Input, Markdown

from src.agent import SecondBrainAgent

# Load environment variables
load_dotenv(".env.local")


class SecondBrainApp(App):
    """Aplikasi TUI Utama dengan Layout & Interaksi Dasar."""

    CSS_PATH = "app.tcss"

    BINDINGS = (
        ("q", "quit", "Quit"),
        ("c", "clear_chat", "Clear Chat"),
        ("escape", "close_viewer", "Close Note"),
    )

    def on_mount(self) -> None:
        self.agent = SecondBrainAgent()

        # Sembunyikan pembaca catatan di awal
        note_viewer = self.query_one("#note-viewer", Markdown)
        note_viewer.display = False

        self.chat_history = [
            "# TUI Second Brain AI Agent Berhasil Aktif!",
            "Ketik pesan di bawah dan tekan Enter. Tekan q untuk keluar."
        ]
        chat_log = self.query_one("#chat-log", Markdown)
        chat_log.update("\n\n".join(self.chat_history))

    def scroll_chat_to_bottom(self, chat_log: Markdown) -> None:
        """Scroll chat log to the bottom."""
        chat_log.scroll_end(animate=False)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        user_text = event.value.strip()
        if not user_text:
            return

        chat_log = self.query_one("#chat-log", Markdown)
        chat_input = self.query_one("#chat-input", Input)

        self.chat_history.append(f"### Anda\n{user_text}")
        self.chat_history.append("*Agent sedang merespon...*")

        chat_log.update("\n\n".join(self.chat_history))
        chat_input.value = ""
        self.scroll_chat_to_bottom(chat_log)

        self.run_worker(self.get_agent_response(user_text))

    async def get_agent_response(self, prompt: str) -> None:
        """Worker asinkron untuk mengambil jawaban dari AI di background."""
        import asyncio

        chat_log = self.query_one("#chat-log", Markdown)

        # Jalankan pemanggilan API AI di background thread
        response = await asyncio.to_thread(self.agent.ask, prompt)

        # Hapus status "sedang merespon"
        if self.chat_history and self.chat_history[-1] == "*Agent sedang merespon...*":
            self.chat_history.pop()

        self.chat_history.append(f"### Agent\n{response}")
        chat_log.update("\n\n".join(self.chat_history))
        self.scroll_chat_to_bottom(chat_log)

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        """Handler ketika file di-klik di sidebar explorer."""
        file_path = event.path
        # Membaca file jika tipenya teks atau markdown
        if file_path.suffix.lower() in (".md", ".txt", ".json", ".py", ".tcss", ".env", ".local"):
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                note_viewer = self.query_one("#note-viewer", Markdown)
                note_viewer.update(content)
                note_viewer.display = True  # Tampilkan panel pembaca catatan!
            except OSError:
                pass

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        vault_path = os.getenv("OBSIDIAN_PATH", ".")
        with Horizontal():
            with Vertical(id="sidebar"):
                yield DirectoryTree(path=vault_path, id="file-tree")

            with Vertical(id="main-content"):
                # Panel Atas: Viewer Catatan Obsidian (Formatted Markdown)
                yield Markdown(
                    "# Pilih Catatan\n\nSilakan pilih file catatan di sidebar kiri untuk membacanya di sini...",
                    id="note-viewer"
                )
                
                # Panel Bawah: AI Agent Chat
                with Vertical(id="chat-area"):
                    yield Markdown(id="chat-log")
                    yield Input(
                        placeholder="Tulis pesan ke Agent di sini...", id="chat-input"
                    )

        yield Footer()

    def action_clear_chat(self) -> None:
        """Aksi ketika menekan tombol 'c' untuk membersihkan log chat."""
        self.chat_history = []
        self.query_one("#chat-log", Markdown).update("")

    def action_close_viewer(self) -> None:
        """Sembunyikan panel pembaca catatan."""
        note_viewer = self.query_one("#note-viewer", Markdown)
        note_viewer.display = False


if __name__ == "__main__":
    app = SecondBrainApp()
    app.run()
