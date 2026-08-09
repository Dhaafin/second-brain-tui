import os
from dotenv import load_dotenv
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DirectoryTree, Footer, Header, Input, Label, Markdown

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
        
        # Posisi & arah untuk animasi peselancar
        self.surf_pos = 0
        self.surf_dir = 1
        self.surf_width = 30
        self.wave_offset = 0
        self.wave_chars = "~≈∽≈"

        chat_log = self.query_one("#chat-log", Markdown)
        chat_log.update("\n\n".join(self.chat_history))

    def scroll_chat_to_bottom(self, chat_log: Markdown) -> None:
        """Scroll chat log to the bottom."""
        chat_log.scroll_end(animate=False)

    def generate_surf_frame(self) -> str:
        """Menghasilkan frame peselancar 🏄 yang bergerak bolak-balik di atas ombak mengalir."""
        # Geser pola ombak ke kanan berdasarkan offset
        wave = "".join(self.wave_chars[(i - self.wave_offset) % len(self.wave_chars)] for i in range(self.surf_width))
        self.wave_offset = (self.wave_offset + 1) % len(self.wave_chars)
        
        pos = self.surf_pos
        # Sisipkan surfer ke baris ombak
        animated_wave = wave[:pos] + "🏄" + wave[pos+1:]
        
        # Update posisi surfer untuk frame selanjutnya
        self.surf_pos += self.surf_dir
        if self.surf_pos >= self.surf_width - 1:
            self.surf_pos = self.surf_width - 1
            self.surf_dir = -1
        elif self.surf_pos <= 0:
            self.surf_pos = 0
            self.surf_dir = 1
            
        return f"🌊 {animated_wave} 🌊 [Tekan ESC untuk cancel]"

    def animate_loading(self) -> None:
        """Menggerakkan animasi peselancar secara periodik."""
        loading_status = self.query_one("#loading-status", Label)
        loading_status.update(self.generate_surf_frame())

    def on_input_submitted(self, event: Input.Submitted) -> None:
        user_text = event.value.strip()
        if not user_text:
            return

        chat_log = self.query_one("#chat-log", Markdown)
        chat_input = self.query_one("#chat-input", Input)
        loading_status = self.query_one("#loading-status", Label)

        # Kunci input agar tidak bisa mengirim pesan ganda saat loading
        chat_input.disabled = True

        self.chat_history.append(f"### Anda\n{user_text}")
        chat_log.update("\n\n".join(self.chat_history))
        chat_input.value = ""
        self.scroll_chat_to_bottom(chat_log)

        # Inisialisasi posisi & tampilkan pembatas loading
        self.surf_pos = 0
        self.surf_dir = 1
        loading_status.display = True
        loading_status.update(self.generate_surf_frame())

        # Jalankan timer animasi surfer (setiap 0.1 detik untuk gerakan mulus)
        self.loading_timer = self.set_interval(0.1, self.animate_loading)

        # Simpan reference worker agar bisa dibatalkan
        self.current_worker = self.run_worker(self.get_agent_response(user_text))

    async def get_agent_response(self, prompt: str) -> None:
        """Worker asinkron untuk mengambil jawaban dari AI di background."""
        import asyncio
        chat_log = self.query_one("#chat-log", Markdown)
        chat_input = self.query_one("#chat-input", Input)
        loading_status = self.query_one("#loading-status", Label)

        try:
            # Jalankan pemanggilan API AI di background thread
            response = await asyncio.to_thread(self.agent.ask, prompt)
            
            # Matikan timer & sembunyikan pembatas loading
            if hasattr(self, "loading_timer"):
                self.loading_timer.stop()
            loading_status.display = False

            # Aktifkan kembali input box
            chat_input.disabled = False
            chat_input.focus()

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
                    yield Label("", id="loading-status")  # Label pembatas loading
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

            # 2. Matikan timer & sembunyikan pembatas loading
            if hasattr(self, "loading_timer"):
                self.loading_timer.stop()
            
            loading_status = self.query_one("#loading-status", Label)
            loading_status.display = False

            # 3. Aktifkan kembali input box
            chat_input = self.query_one("#chat-input", Input)
            chat_input.disabled = False
            chat_input.focus()

            self.chat_history.append("### Agent\n*(X) Pencarian dibatalkan oleh Anda (Agnes terjatuh dari papan selancar 🏄💥...)*")
            
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
