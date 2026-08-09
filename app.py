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
        ("escape", "close_viewer", "Close Note / Cancel Agent"),
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
        
        # Frame animasi goofy untuk status loading
        self.loading_frames = [
            "ヘ(°￢°)ノ *Agnes sedang mengendus-endus catatan Anda...*",
            "┌|°_°|┘ *Agnes sedang joget koplo di background thread...*",
            "(;°_°) *Agnes panik mencari file yang Anda maksud...*",
            "ヘ(._.ヘ) *Agnes sedang merangkak menyusuri file markdown...*",
            "ε=ε=┌(;°_°)┘ *Agnes berlari kencang mengambil data...*"
        ]
        self.current_frame_idx = 0

        chat_log = self.query_one("#chat-log", Markdown)
        chat_log.update("\n\n".join(self.chat_history))

    def scroll_chat_to_bottom(self, chat_log: Markdown) -> None:
        """Scroll chat log to the bottom."""
        chat_log.scroll_end(animate=False)

    def animate_loading(self) -> None:
        """Menggerakkan frame animasi goofy secara periodik."""
        chat_log = self.query_one("#chat-log", Markdown)
        
        if self.chat_history and self.chat_history[-1] in self.loading_frames:
            self.chat_history.pop()
            
        self.current_frame_idx = (self.current_frame_idx + 1) % len(self.loading_frames)
        self.chat_history.append(self.loading_frames[self.current_frame_idx])
        chat_log.update("\n\n".join(self.chat_history))
        self.scroll_chat_to_bottom(chat_log)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        user_text = event.value.strip()
        if not user_text:
            return

        chat_log = self.query_one("#chat-log", Markdown)
        chat_input = self.query_one("#chat-input", Input)

        # Kunci input agar tidak bisa mengirim pesan ganda saat loading
        chat_input.disabled = True

        self.chat_history.append(f"### Anda\n{user_text}")
        self.chat_history.append(self.loading_frames[0])

        chat_log.update("\n\n".join(self.chat_history))
        chat_input.value = ""
        self.scroll_chat_to_bottom(chat_log)

        # Aktifkan animasi goofy setiap 0.4 detik
        self.loading_timer = self.set_interval(0.4, self.animate_loading)

        # Simpan reference worker agar bisa dibatalkan
        self.current_worker = self.run_worker(self.get_agent_response(user_text))

    async def get_agent_response(self, prompt: str) -> None:
        """Worker asinkron untuk mengambil jawaban dari AI di background."""
        import asyncio
        chat_log = self.query_one("#chat-log", Markdown)
        chat_input = self.query_one("#chat-input", Input)

        try:
            # Jalankan pemanggilan API AI di background thread
            response = await asyncio.to_thread(self.agent.ask, prompt)
            
            # Matikan timer animasi
            if hasattr(self, "loading_timer"):
                self.loading_timer.stop()

            # Aktifkan kembali input box
            chat_input.disabled = False
            chat_input.focus()

            # Hapus frame loading terakhir
            if self.chat_history and self.chat_history[-1] in self.loading_frames:
                self.chat_history.pop()

            self.chat_history.append(f"### Agent\n{response}")
            chat_log.update("\n\n".join(self.chat_history))
            self.scroll_chat_to_bottom(chat_log)
        except asyncio.CancelledError:
            # Penanganan pembatalan sudah di-handle oleh action_close_viewer
            pass

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
        """Sembunyikan panel pembaca catatan ATAU batalkan pencarian Agent jika sedang berjalan."""
        if hasattr(self, "current_worker") and self.current_worker.is_running:
            # 1. Batalkan background worker
            self.current_worker.cancel()

            # 2. Matikan timer animasi
            if hasattr(self, "loading_timer"):
                self.loading_timer.stop()

            # 3. Aktifkan kembali input box
            chat_input = self.query_one("#chat-input", Input)
            chat_input.disabled = False
            chat_input.focus()

            # 4. Hapus frame loading
            if self.chat_history and self.chat_history[-1] in self.loading_frames:
                self.chat_history.pop()

            self.chat_history.append("### Agent\n*(X) Pencarian dibatalkan oleh Anda (Agnes menangis tersedu-sedu di pojok terminal...)*")
            
            chat_log = self.query_one("#chat-log", Markdown)
            chat_log.update("\n\n".join(self.chat_history))
            self.scroll_chat_to_bottom(chat_log)
        else:
            # Sembunyikan panel Note Viewer
            note_viewer = self.query_one("#note-viewer", Markdown)
            note_viewer.display = False


if __name__ == "__main__":
    app = SecondBrainApp()
    app.run()
