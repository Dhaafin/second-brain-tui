import os
from dotenv import load_dotenv
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DirectoryTree, Footer, Header, Input, TextArea

from src.agent import SecondBrainAgent

# Load environment variables
load_dotenv(".env.local")


class SecondBrainApp(App):
    """Aplikasi TUI Utama dengan Layout & Interaksi Dasar."""

    CSS_PATH = "app.tcss"

    BINDINGS = (
        ("q", "quit", "Quit"),
        ("c", "clear_chat", "Clear Chat"),
    )

    def on_mount(self) -> None:
        self.agent = SecondBrainAgent()

        chat_log = self.query_one("#chat-log", TextArea)
        chat_log.text = (
            "TUI Second Brain AI Agent Berhasil Aktif!\n"
            "Ketik pesan di bawah dan tekan Enter. Tekan q untuk keluar.\n"
        )

    def scroll_chat_to_bottom(self, chat_log: TextArea) -> None:
        """Scroll chat log to the bottom by placing the cursor at the end."""
        lines = chat_log.text.split("\n")
        if lines:
            last_line_idx = len(lines) - 1
            last_char_idx = len(lines[-1])
            chat_log.cursor_location = (last_line_idx, last_char_idx)
        chat_log.scroll_end(animate=False)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        user_text = event.value.strip()
        if not user_text:
            return

        chat_log = self.query_one("#chat-log", TextArea)
        chat_input = self.query_one("#chat-input", Input)

        chat_log.text += f"\nAnda: {user_text}\n"
        chat_input.value = ""

        chat_log.text += "Agent sedang merespon...\n"
        self.scroll_chat_to_bottom(chat_log)

        self.run_worker(self.get_agent_response(user_text))

    async def get_agent_response(self, prompt: str) -> None:
        """Worker asinkron untuk mengambil jawaban dari AI di background."""
        import asyncio

        chat_log = self.query_one("#chat-log", TextArea)

        # Jalankan pemanggilan API AI di background thread
        response = await asyncio.to_thread(self.agent.ask, prompt)

        # Hapus status "sedang merespon" dan tampilkan jawaban AI asli
        current_text = chat_log.text
        if "Agent sedang merespon...\n" in current_text:
            chat_log.text = current_text.replace("Agent sedang merespon...\n", f"Agent: {response}\n")
        else:
            chat_log.text += f"Agent: {response}\n"

        self.scroll_chat_to_bottom(chat_log)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        vault_path = os.getenv("OBSIDIAN_PATH", ".")
        with Horizontal():
            with Vertical(id="sidebar"):
                yield DirectoryTree(path=vault_path, id="file-tree")

            with Vertical(id="chat-area"):
                yield TextArea(read_only=True, show_line_numbers=False, id="chat-log")
                yield Input(
                    placeholder="Tulis pesan ke Agent di sini...", id="chat-input"
                )

        yield Footer()

    def action_clear_chat(self) -> None:
        """Aksi ketika menekan tombol 'c' untuk membersihkan log chat."""
        self.query_one("#chat-log", TextArea).text = ""


if __name__ == "__main__":
    app = SecondBrainApp()
    app.run()
