import os
import asyncio
from textual.widgets import Input, Label, Markdown, OptionList
from textual.containers import Vertical
from src.agent import SecondBrainAgent

class FocusableMarkdown(Markdown):
    """Markdown widget that can accept focus for keyboard scrolling."""
    can_focus = True

class ChatPanel(Vertical):
    def compose(self):
        yield FocusableMarkdown(id="chat-log")
        yield Label("", id="loading-status")
        yield OptionList(id="mention-autocomplete")
        yield Input(
            placeholder="Type a message to the Agent here...", id="chat-input"
        )

    def on_mount(self) -> None:
        self.query_one("#mention-autocomplete").display = False
        self.chat_history = [
            "# TUI Second Brain AI Agent Active!",
            "Type a message below and press Enter. Press Q to exit."
        ]
        self.surf_pos = 0
        self.surf_dir = 1
        self.surf_width = 30
        self.wave_offset = 0
        self.wave_chars = "~≈∽≈"
        
        chat_log = self.query_one("#chat-log", Markdown)
        chat_log.update("\n\n".join(self.chat_history))

    def scroll_chat_to_bottom(self, chat_log: Markdown) -> None:
        chat_log.scroll_end(animate=False)

    def generate_surf_frame(self) -> str:
        wave = "".join(self.wave_chars[(i - self.wave_offset) % len(self.wave_chars)] for i in range(self.surf_width))
        self.wave_offset = (self.wave_offset + 1) % len(self.wave_chars)
        pos = self.surf_pos
        animated_wave = wave[:pos] + "🏄" + wave[pos+1:]
        
        self.surf_pos += self.surf_dir
        if self.surf_pos >= self.surf_width - 1:
            self.surf_pos = self.surf_width - 1
            self.surf_dir = -1
        elif self.surf_pos <= 0:
            self.surf_pos = 0
            self.surf_dir = 1
            
        return f"🌊 {animated_wave} 🌊"

    def animate_loading(self) -> None:
        loading_status = self.query_one("#loading-status", Label)
        self.elapsed_time += 0.1
        dots = "." * (int(self.elapsed_time * 2) % 3 + 1)
        dots_fixed = dots.ljust(3, " ")
        wave_part = self.generate_surf_frame()
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

        chat_input.disabled = True
        self.chat_history.append(f"### You\n{user_text}")
        chat_log.update("\n\n".join(self.chat_history))
        chat_input.value = ""
        self.scroll_chat_to_bottom(chat_log)

        self.surf_pos = 0
        self.surf_dir = 1
        self.elapsed_time = 0.0
        self.current_agent_status = "is thinking"
        loading_status.display = True

        self.loading_timer = self.set_interval(0.1, self.animate_loading)
        self.current_worker = self.run_worker(self.get_agent_response(user_text))

    async def get_agent_response(self, prompt: str) -> None:
        chat_log = self.query_one("#chat-log", Markdown)
        chat_input = self.query_one("#chat-input", Input)
        loading_status = self.query_one("#loading-status", Label)

        try:
            def update_status(status_text: str):
                self.current_agent_status = status_text

            if getattr(self.app.agent, "awaiting_onboarding_consent", False):
                response = self.app.agent.process_onboarding(prompt)
                await asyncio.sleep(0.5)
            else:
                response = await asyncio.to_thread(self.app.agent.ask, prompt, update_status)
            
            if hasattr(self, "loading_timer"):
                self.loading_timer.stop()
            loading_status.display = False

            chat_input.disabled = False
            chat_input.focus()

            self.chat_history.append(f"### Agent\n{response}")
            chat_log.update("\n\n".join(self.chat_history))
            self.scroll_chat_to_bottom(chat_log)
            self.app.query_one("#file-tree").reload()
        except asyncio.CancelledError:
            pass

    def on_input_changed(self, event: Input.Changed) -> None:
        value = event.value
        if "@" in value:
            parts = value.split(" ")
            last_part = parts[-1]
            if last_part.startswith("@"):
                query = last_part[1:].lower()
                self.show_mention_autocomplete(query)
                return
        self.hide_mention_autocomplete()

    def show_mention_autocomplete(self, query: str) -> None:
        autocomplete = self.query_one("#mention-autocomplete", OptionList)
        autocomplete.clear_options()

        from src.vault import get_all_note_paths
        all_paths = get_all_note_paths(self.app.agent.vault_path)
        
        matches = []
        for p in all_paths:
            filename = os.path.basename(p)
            if query in filename.lower():
                matches.append(filename)

        matches = matches[:5]
        if matches:
            for match in matches:
                autocomplete.add_option(match)
            autocomplete.display = True
        else:
            autocomplete.display = False

    def hide_mention_autocomplete(self) -> None:
        autocomplete = self.query_one("#mention-autocomplete", OptionList)
        autocomplete.display = False

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        selected_option = event.option.prompt
        chat_input = self.query_one("#chat-input", Input)

        value = chat_input.value
        parts = value.split(" ")
        
        if " " in selected_option:
            replacement = f'@"{selected_option}"'
        else:
            replacement = f"@{selected_option}"

        parts[-1] = replacement
        new_value = " ".join(parts) + " "
        chat_input.value = new_value

        self.hide_mention_autocomplete()
        chat_input.focus()

    def on_key(self, event) -> None:
        if event.key == "down" and self.query_one("#mention-autocomplete").display:
            self.query_one("#mention-autocomplete").focus()
