import os
from dotenv import load_dotenv
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DirectoryTree, Footer, Header, Input, Label, Markdown

from src.agent import SecondBrainAgent

# Load environment variables
load_dotenv(".env.local")


class FocusableMarkdown(Markdown):
    """Markdown widget that can accept focus for keyboard scrolling."""
    can_focus = True


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

        # Sembunyikan container pembaca catatan di awal
        self.query_one("#note-viewer-container").display = False

        self.chat_history = [
            "# TUI Second Brain AI Agent Active!",
            "Type a message below and press Enter. Press Q to exit."
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
            
        return f"🌊 {animated_wave} 🌊"

    def animate_loading(self) -> None:
        """Menggerakkan animasi peselancar & stopwatch secara periodik."""
        loading_status = self.query_one("#loading-status", Label)
        self.elapsed_time += 0.1
        
        # Efek titik-titik loading bergerak (cycle setiap 0.5 detik)
        dots = "." * (int(self.elapsed_time * 2) % 3 + 1)
        dots_fixed = dots.ljust(3, " ")  # Lebar tetap agar teks tidak geser/bergetar
        
        wave_part = self.generate_surf_frame()
        # Dapatkan status terakhir dari agen, default "is thinking"
        current_status = getattr(self, "current_agent_status", "is thinking")
        
        loading_status.update(
            f"{wave_part} | Agnes {current_status}{dots_fixed} ({self.elapsed_time:.1f}s) | [ESC to Cancel]"
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        user_text = event.value.strip()
        if not user_text:
            return

        chat_log = self.query_one("#chat-log", Markdown)
        chat_input = self.query_one("#chat-input", Input)
        loading_status = self.query_one("#loading-status", Label)

        # Kunci input agar tidak bisa mengirim pesan ganda saat loading
        chat_input.disabled = True

        self.chat_history.append(f"### You\n{user_text}")
        chat_log.update("\n\n".join(self.chat_history))
        chat_input.value = ""
        self.scroll_chat_to_bottom(chat_log)

        # Inisialisasi posisi & tampilkan pembatas loading
        self.surf_pos = 0
        self.surf_dir = 1
        self.elapsed_time = 0.0
        self.current_agent_status = "is thinking"
        loading_status.display = True

        # Jalankan timer animasi surfer & stopwatch (setiap 0.1 detik)
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
            # Callback untuk memperbarui status agen
            def update_status(status_text: str):
                self.current_agent_status = status_text

            # Jalankan pemanggilan API AI di background thread
            response = await asyncio.to_thread(self.agent.ask, prompt, update_status)
            
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
            self.query_one("#file-tree", DirectoryTree).reload()
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
                self.query_one("#note-viewer-title", Label).update(f"📄 {file_path.name}")
                self.query_one("#note-viewer-container").display = True  # Tampilkan container!
            except OSError:
                pass

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        vault_path = os.getenv("OBSIDIAN_PATH", ".")
        with Horizontal():
            with Vertical(id="sidebar"):
                yield DirectoryTree(path=vault_path, id="file-tree")

            with Vertical(id="main-content"):
                # Top Panel: Obsidian Note Viewer Container with Header & Focusable Markdown
                with Vertical(id="note-viewer-container"):
                    with Horizontal(id="note-viewer-header"):
                        yield Label("📄 Note Viewer", id="note-viewer-title")
                        yield Button("X", id="close-note-btn", variant="error")
                    yield FocusableMarkdown(
                        "# Select a Note\n\nPlease select a note from the left sidebar to read it here...",
                        id="note-viewer"
                    )
                
                # Panel Bawah: AI Agent Chat
                with Vertical(id="chat-area"):
                    yield Markdown(id="chat-log")
                    yield Label("", id="loading-status")  # Label pembatas loading
                    yield Input(
                        placeholder="Type a message to the Agent here...", id="chat-input"
                    )

        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handler ketika tombol X diklik untuk menutup note viewer."""
        if event.button.id == "close-note-btn":
            self.action_close_viewer()

    def action_clear_chat(self) -> None:
        """Aksi ketika menekan tombol 'c' untuk membersihkan log chat."""
        self.chat_history = []
        self.agent.clear_history()
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

            self.chat_history.append("### Agent\n*(X) Search cancelled by user (Agnes fell off her surfboard 🏄💥...)*")
            
            chat_log = self.query_one("#chat-log", Markdown)
            chat_log.update("\n\n".join(self.chat_history))
            self.scroll_chat_to_bottom(chat_log)
        else:
            # Sembunyikan panel Note Viewer Container
            self.query_one("#note-viewer-container").display = False


if __name__ == "__main__":
    app = SecondBrainApp()
    app.run()
