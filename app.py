from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DirectoryTree, Footer, Header, Input, RichLog


class SecondBrainApp(App):
    """Aplikasi TUI Utama dengan Layout & Interaksi Dasar."""

    CSS_PATH = "app.tcss"

    BINDINGS = (
        ("q", "quit", "Quit"),
        ("c", "clear_chat", "Clear Chat"),
    )

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

    def on_mount(self) -> None:
        """Dipanggil saat aplikasi pertama kali terbuka di layar."""
        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.write(
            "[bold green]TUI Second Brain AI Agent Berhasil Aktif![/bold green]"
        )
        chat_log.write(
            "Ketik pesan di bawah dan tekan [bold yellow]Enter[/bold yellow]. Tekan [bold yellow]q[/bold yellow] untuk keluar."
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Dipanggil saat user menekan Enter di kolom input."""
        user_text = event.value.strip()
        if not user_text:
            return

        chat_log = self.query_one("#chat-log", RichLog)
        chat_input = self.query_one("#chat-input", Input)

        # 1. Cetak teks ketikan user ke log chat
        chat_log.write(f"\n[bold cyan]Anda:[/bold cyan] {user_text}")

        # 2. Bersihkan kolom input
        chat_input.value = ""

        # 3. Jalankan efek "menunggu" respon AI di background
        chat_log.write("[italic gray]Agent sedang merespon...[/italic gray]")

    def action_clear_chat(self) -> None:
        """Aksi ketika menekan tombol 'c' untuk membersihkan log chat."""
        self.query_one("#chat-log", RichLog).clear()


if __name__ == "__main__":
    app = SecondBrainApp()
    app.run()
