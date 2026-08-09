from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DirectoryTree, Footer, Header, Input, RichLog

from src.agent import SecondBrainAgent


class SecondBrainApp(App):
    """Aplikasi TUI Utama dengan Layout & Interaksi Dasar."""

    CSS_PATH = "app.tcss"

    BINDINGS = (
        ("q", "quit", "Quit"),
        ("c", "clear_chat", "Clear Chat"),
    )

    def on_mount(self) -> None:
        self.agent = SecondBrainAgent()

        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.write(
            "[bold green]TUI Second Brain AI Agent Berhasil Aktif![/bold green]"
        )
        chat_log.write("Ketik pesan di bawah dan tekan Enter. Tekan q untuk keluar.")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        user_text = event.value.strip()
        if not user_text:
            return

        chat_log = self.query_one("#chat-log", RichLog)
        chat_input = self.query_one("#chat-input", Input)

        chat_log.write(f"\n[bold cyan]Anda:[/bold cyan] {user_text}")
        chat_input.value = ""

        chat_log.write("[italic gray]Agent sedang merespon...[/italic gray]")

        self.run_worker(self.get_agent_response(user_text))

    async def get_agent_response(self, prompt: str) -> None:
        """Worker asinkron untuk mengambil jawaban dari AI di background."""
        import asyncio

        chat_log = self.query_one("#chat-log", RichLog)

        # Jalankan pemanggilan API AI di background thread
        response = await asyncio.to_thread(self.agent.ask, prompt)

        # Tampilkan hasil jawaban AI ke layar chat log
        chat_log.write(f"[bold magenta]Agent:[/bold magenta] {response}")

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal():
            with Vertical(id="sidebar"):
                yield DirectoryTree(path=".", id="file-tree")

            with Vertical(id="chat-area"):
                yield RichLog(id="chat-log", highlight=True, markup=True)
                yield Input(
                    placeholder="Tulis pesan ke Agent di sini...", id="chat-input"
                )

        yield Footer()

    def action_clear_chat(self) -> None:
        """Aksi ketika menekan tombol 'c' untuk membersihkan log chat."""
        self.query_one("#chat-log", RichLog).clear()


if __name__ == "__main__":
    app = SecondBrainApp()
    app.run()
