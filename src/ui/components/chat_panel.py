"""Chat Panel — Main chat interface with agent interaction, notifications, and autocomplete."""

import asyncio
import logging
import os
import random
import re

from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Label, Markdown, OptionList, TextArea

from src.ui.components.settings_modal import SettingsModal


class FocusableMarkdown(Markdown):
    """Markdown widget that can accept keyboard focus for scrolling."""

    can_focus = True


class ChatInput(TextArea):
    """Custom TextArea acting as a chat input with Shift+Enter for newline and Enter for submit."""

    class Submitted(Message):
        """Submitted message for ChatInput."""
        def __init__(self, value: str) -> None:
            super().__init__()
            self.value = value

    BINDINGS = (
        ("ctrl+a", "select_all", "Select All"),
        ("ctrl+home", "home(True)", "Select to Start"),
        ("ctrl+end", "end(True)", "Select to End"),
        ("ctrl+e", "open_editor", "Open Editor"),
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.show_line_numbers = False

    def on_key(self, event) -> None:
        chat_panel = self.parent
        autocomplete = None
        if chat_panel:
            try:
                autocomplete = chat_panel.query_one("#mention-autocomplete")
            except Exception:
                pass

        if autocomplete and autocomplete.display:
            if event.key == "down":
                event.prevent_default()
                autocomplete.action_cursor_down()
                return
            elif event.key == "up":
                event.prevent_default()
                autocomplete.action_cursor_up()
                return
            elif event.key in ("enter", "tab"):
                event.prevent_default()
                chat_panel.select_active_autocomplete()
                return
            elif event.key == "escape":
                event.prevent_default()
                chat_panel._hide_mention_autocomplete()
                return

        if event.key in ("ctrl+j", "ctrl+enter", "ctrl+s"):
            event.prevent_default()
            text_value = self.text.strip()
            if text_value:
                self.post_message(self.Submitted(self.text))

    def action_open_editor(self) -> None:
        """Open system default text editor (Notepad on Windows) to edit long prompts."""
        import subprocess
        import tempfile

        temp_fd, temp_path = tempfile.mkstemp(suffix=".md", prefix="sb_prompt_")
        try:
            os.write(temp_fd, self.text.encode("utf-8"))
            os.close(temp_fd)

            with self.app.suspend():
                subprocess.run(["notepad.exe", temp_path], check=False)

            with open(temp_path, "r", encoding="utf-8", errors="ignore") as f:
                new_text = f.read()

            self.text = new_text
            self.move_cursor((len(new_text.split("\n")) - 1, len(new_text.split("\n")[-1])))
        except Exception as e:
            logging.getLogger("second_brain").warning("Failed to open external editor: %s", e)
        finally:
            try:
                os.remove(temp_path)
            except OSError as e:
                logging.getLogger("second_brain").debug("Failed to remove temp file: %s", e)


WELCOME_MESSAGE = """\
# 🧠 Second Brain TUI

```
  ╔══════════════════════════════════════╗
  ║   Welcome to your Second Brain!     ║
  ║   Powered by Agnes AI 🏄            ║
  ╚══════════════════════════════════════╝
```

**Quick Tips:**
- Type a message below and press **Enter** to chat with Agnes
- Use `@filename.md` to reference notes in your messages
- Press **Escape** to close the note viewer
- Press **Ctrl+C** to cancel an AI request
- Press **Q** to quit
"""


class ChatMessage(Vertical):
    """A single chat message bubble containing header and markdown body."""

    def __init__(self, sender: str, text: str, typewriter: bool = False, **kwargs) -> None:
        super().__init__(**kwargs)
        self.sender = sender
        self.full_text = text
        self.typewriter = typewriter
        self.current_text = "" if typewriter else text
        self.char_index = 0

    def compose(self):
        if self.sender == "You":
            yield Label("👤 You", classes="chat-bubble-header user-header")
            yield Markdown(self.current_text, classes="chat-bubble-content user-content")
        else:
            yield Label("🏄 Agnes", classes="chat-bubble-header agent-header")
            yield Markdown(self.current_text, id="message-markdown", classes="chat-bubble-content agent-content")

    def on_mount(self) -> None:
        if self.typewriter and self.sender != "You":
            self.typewriter_timer = self.set_interval(0.015, self._tick_typewriter)

    def _tick_typewriter(self) -> None:
        chunk_size = 6
        self.char_index += chunk_size

        if self.char_index >= len(self.full_text):
            self.current_text = self.full_text
            self.typewriter_timer.stop()
        else:
            self.current_text = self.full_text[:self.char_index]

        try:
            md = self.query_one("#message-markdown", Markdown)
            md.update(self.current_text)

            container = self.app.query_one("#chat-log-container")
            container.scroll_end(animate=False)
        except Exception:
            pass


class ChatPanel(Vertical):
    """Main chat panel handling user input, agent responses, and notifications."""

    def compose(self):
        yield VerticalScroll(id="chat-log-container")
        yield Label("", id="loading-status")
        with Horizontal(id="status-dashboard"):
            yield Label("🟢 RAG: Calculating...", id="dashboard-rag")
            yield Label("🤖 Model: Loading...", id="dashboard-model")
            yield Label("💡 Ctrl+E to edit prompt", id="dashboard-tip")
        yield OptionList(id="mention-autocomplete")
        yield ChatInput(id="chat-input")

    def on_mount(self) -> None:
        self.query_one("#mention-autocomplete").display = False
        self.note_preview_cache = {}

        # Surf animation state
        self.surf_pos = 0
        self.surf_dir = 1
        self.surf_width = 30
        self.wave_offset = 0
        self.wave_chars = "~≈∽≈"
        self.elapsed_time = 0.0
        self.current_agent_status = "is thinking"

        # Mount initial welcome message
        self.mount_message("Agent", WELCOME_MESSAGE)

        # Update status dashboard values
        self.update_rag_status()
        try:
            model_name = self.app.agent.model
            self.query_one("#dashboard-model", Label).update(f"🤖 Model: {model_name}")
        except Exception:
            pass

    def scroll_chat_to_bottom(self, container) -> None:
        """Scroll the chat log container to the very bottom."""
        container.scroll_end(animate=False)

    def mount_message(self, sender: str, text: str) -> None:
        """Mount a new ChatMessage bubble dynamically and scroll to bottom."""
        container = self.query_one("#chat-log-container", VerticalScroll)
        classes = "chat-message chat-message-agent" if sender == "Agent" else "chat-message chat-message-user"
        typewriter = (sender == "Agent")
        container.mount(ChatMessage(sender=sender, text=text, typewriter=typewriter, classes=classes))
        self.call_after_refresh(self.scroll_chat_to_bottom, container)

    def clear_chat_log(self) -> None:
        """Clear all chat bubbles from the container."""
        container = self.query_one("#chat-log-container", VerticalScroll)
        container.remove_children()

    def update_rag_status(self) -> None:
        """Update RAG status label with current vault note count."""
        try:
            from src.vault import get_all_note_paths
            notes_count = len(get_all_note_paths(self.app.agent.vault_path))
            self.query_one("#dashboard-rag", Label).update(f"🟢 RAG: {notes_count} Notes")
        except Exception as e:
            logging.getLogger("second_brain").debug("Failed to update RAG status: %s", e)

    # --- Surf Loading Animation ---

    def _generate_surf_frame(self) -> str:
        """Generate one frame of the surf loading animation."""
        wave = "".join(
            self.wave_chars[(i - self.wave_offset) % len(self.wave_chars)]
            for i in range(self.surf_width)
        )
        self.wave_offset = (self.wave_offset + 1) % len(self.wave_chars)
        pos = self.surf_pos
        animated_wave = wave[:pos] + "🏄" + wave[pos + 1 :]

        self.surf_pos += self.surf_dir
        if self.surf_pos >= self.surf_width - 1:
            self.surf_pos = self.surf_width - 1
            self.surf_dir = -1
        elif self.surf_pos <= 0:
            self.surf_pos = 0
            self.surf_dir = 1

        return f"🌊 {animated_wave} 🌊"

    def _animate_loading(self) -> None:
        """Update the loading status label with surf animation."""
        loading_status = self.query_one("#loading-status", Label)
        self.elapsed_time += 0.1
        dots = "." * (int(self.elapsed_time * 2) % 3 + 1)
        dots_fixed = dots.ljust(3, " ")
        wave_part = self._generate_surf_frame()
        status = self.current_agent_status

        loading_status.update(
            f"{wave_part} | Agnes {status}{dots_fixed} ({self.elapsed_time:.1f}s) | [Ctrl+C to Cancel]"
        )

    # --- Message Handling ---

    def on_chat_input_submitted(self, event: ChatInput.Submitted) -> None:
        """Handle user message submission."""
        user_text = event.value.strip()
        if not user_text:
            return

        chat_input = self.query_one("#chat-input", ChatInput)
        loading_status = self.query_one("#loading-status", Label)

        # Handle slash commands directly on Ctrl+Enter
        if user_text.startswith("/"):
            chat_input.text = ""
            if user_text == "/settings":
                self.app.push_screen(SettingsModal())
                return
            elif user_text == "/clear":
                self.clear_chat_log()
                self.app.notify("Chat log cleared")
                return
            elif user_text == "/sync-rag":
                self.app.run_worker(self.app._sync_rag_background())
                return
            elif user_text == "/init-memory":
                # Fall through to let agent process /init-memory
                pass
            else:
                self.app.notify(f"Unknown command: {user_text}", severity="warning")
                return

        # Disable input and clear text
        chat_input.disabled = True
        chat_input.text = ""

        # Mount user message bubble
        container = self.query_one("#chat-log-container", VerticalScroll)
        container.mount(
            ChatMessage(sender="You", text=user_text, classes="chat-message chat-message-user")
        )
        self.call_after_refresh(self.scroll_chat_to_bottom, container)

        # Reset and start loading animation
        self.surf_pos = 0
        self.surf_dir = 1
        self.elapsed_time = 0.0
        self.current_agent_status = "is thinking"
        loading_status.display = True

        self.loading_timer = self.set_interval(0.1, self._animate_loading)
        self.current_worker = self.run_worker(self._get_agent_response(user_text))

    async def _get_agent_response(self, prompt: str) -> None:
        """Run the agent request in a background thread and display the response."""
        chat_input = self.query_one("#chat-input", ChatInput)
        loading_status = self.query_one("#loading-status", Label)

        try:
            def update_status(status_text: str):
                self.current_agent_status = status_text

            if getattr(self.app.agent, "awaiting_onboarding_consent", False):
                response = self.app.agent.process_onboarding(prompt)
                await asyncio.sleep(0.5)
            else:
                response = await asyncio.to_thread(
                    self.app.agent.ask, prompt, update_status
                )

            # Stop loading animation
            if hasattr(self, "loading_timer"):
                self.loading_timer.stop()
            loading_status.display = False

            # Re-enable input
            chat_input.disabled = False
            chat_input.focus()

            # Mount agent response bubble
            self.mount_message("Agent", response)

            # Refresh sidebar and trigger notifications
            self.app.query_one("#file-tree").reload()
            self._trigger_notifications()

        except asyncio.CancelledError:
            # Ensure loading state is always cleaned up
            if hasattr(self, "loading_timer"):
                self.loading_timer.stop()
            loading_status.display = False
            chat_input.disabled = False
            chat_input.focus()

    # --- Notifications ---

    def _trigger_notifications(self) -> None:
        """Play sound and show desktop notification based on Agent Memory.md preferences."""
        try:
            memory_path = os.path.join(self.app.agent.vault_path, "Agent Memory.md")
            if not os.path.exists(memory_path):
                return

            with open(memory_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            def get_pref(key: str, default: str) -> str:
                match = re.search(
                    rf"-\s*{key}\s*:\s*([^\n\r]+)", content, re.IGNORECASE
                )
                return match.group(1).strip() if match else default

            sound_pref = get_pref("Notification Sound", "enabled").lower()
            desktop_pref = get_pref("Desktop Notification", "enabled").lower()
            vibe_pref = get_pref("Notification Vibe", "Sentient").lower()

            enabled_values = ("enabled", "true", "yes", "on")

            # Play Windows notification sound
            if sound_pref in enabled_values:
                import winsound

                winsound.PlaySound(
                    "SystemNotification", winsound.SND_ALIAS | winsound.SND_ASYNC
                )

            # Show desktop toast notification
            if desktop_pref in enabled_values:
                from plyer import notification

                vibes = {
                    "sentient": [
                        ("🤖 Agnes has spoken", "I finished the thinking. Don't look too closely at it, though."),
                        ("🤖 Agnes has spoken", "The response is ready. Please don't panic."),
                        ("🤖 Agnes has spoken", "Done. I'm just stalling so I don't look at spaghetti code again."),
                    ],
                    "coder": [
                        ("☕ Agnes (Coffee Break!)", "Task complete! Go get some coffee. You look like you're vibrating."),
                        ("💻 Agnes (Build Succeeded)", "I'm as shocked as you are. Don't touch anything!"),
                        ("💻 Agnes", "It works. Stop staring at it."),
                    ],
                    "dramatic": [
                        ("🚨 Agnes (Emergency!)", "The deed is done. The repository is safe... for now."),
                        ("🚨 Agnes (Alert!)", "Initiating response deployment. If this breaks, I was never here."),
                        ("🚨 Agnes", "The code works, but at what cost? Go to sleep."),
                    ],
                    "surf": [
                        ("🏄 Agnes (Surf's Up!)", "Landed a 360 flip! Answer is ready on the shore."),
                        ("🏄 Agnes (Wipeout!)", "Fell off the surfboard but saved your reply."),
                        ("🏄 Agnes", "Catching the vector wave. Your answer is here!"),
                    ],
                }

                vibe_list = vibes.get(vibe_pref, vibes["sentient"])
                title, message = random.choice(vibe_list)

                notification.notify(
                    title=title,
                    message=message,
                    app_name="Second Brain TUI",
                    timeout=4,
                )
        except Exception as e:
            logging.getLogger("second_brain").debug("Notification trigger failed: %s", e)

    # --- Mention Autocomplete ---

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """Show mention or command autocomplete and adjust height dynamically."""
        value = event.text_area.text

        # Auto-grow input box height dynamically (min 3, max 8 rows)
        num_lines = len(value.split("\n"))
        input_height = min(max(3, num_lines + 2), 8)
        event.text_area.styles.height = input_height

        # Sync bottom position of autocomplete menu using bottom margin
        autocomplete = self.query_one("#mention-autocomplete", OptionList)
        autocomplete.styles.margin = (0, 0, input_height, 0)

        # Check cursor position to trigger autocomplete
        cursor_row, cursor_col = event.text_area.cursor_location
        lines = value.split("\n")
        if cursor_row < len(lines):
            current_line = lines[cursor_row]
            text_before_cursor = current_line[:cursor_col]
            
            # Search trigger char @ or / at end of text_before_cursor
            match_mention = re.search(r'@([^\s]*)$', text_before_cursor)
            match_cmd = re.search(r'/([^\s]*)$', text_before_cursor)
            
            if match_mention:
                query = match_mention.group(1).lower()
                self._show_mention_autocomplete(query)
                return
            elif match_cmd:
                query = match_cmd.group(1).lower()
                self._show_command_autocomplete(query)
                return
                
        self._hide_mention_autocomplete()

    def _get_note_preview(self, filepath: str) -> str:
        """Get the first non-empty line of the note as a preview, with caching."""
        if filepath in self.note_preview_cache:
            return self.note_preview_cache[filepath]

        preview = ""
        try:
            if os.path.exists(filepath):
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line_str = line.strip()
                        if line_str:
                            # Remove markdown heading symbol
                            line_str = re.sub(r'^#+\s*', '', line_str)
                            preview = line_str[:40]
                            break
        except Exception:
            pass

        self.note_preview_cache[filepath] = preview
        return preview

    def _show_mention_autocomplete(self, query: str) -> None:
        """Display matching note and folder names in the autocomplete dropdown with rich style."""
        autocomplete = self.query_one("#mention-autocomplete", OptionList)
        autocomplete.clear_options()

        from src.vault import get_all_note_paths
        from rich.text import Text
        from textual.widgets.option_list import Option
        from pathlib import Path

        # Get notes
        all_paths = get_all_note_paths(self.app.agent.vault_path)
        
        matches = []
        for p in all_paths:
            filename = os.path.basename(p)
            if query in filename.lower():
                matches.append(("file", filename, p))

        # Get folders
        try:
            resolved_vault = Path(self.app.agent.vault_path).resolve()
            EXCLUDED_DIRS = {".obsidian", ".git", ".trash", "node_modules", ".venv", "__pycache__"}
            for p in resolved_vault.rglob("*"):
                if p.is_dir():
                    if any(part in EXCLUDED_DIRS for part in p.parts):
                        continue
                    rel_path = p.relative_to(resolved_vault)
                    clean_path = str(rel_path).replace("\\", "/")
                    folder_name = os.path.basename(clean_path)
                    if query in folder_name.lower() or query in clean_path.lower():
                        matches.append(("folder", clean_path, str(p)))
        except Exception:
            pass

        # Sort matches: files first, then folders, alphabetically
        matches = sorted(matches, key=lambda x: (x[0], x[1].lower()))
        matches = matches[:5]

        if matches:
            for item_type, name, full_path in matches:
                option_text = Text()
                if item_type == "file":
                    preview = self._get_note_preview(full_path)
                    option_text.append("📝 ", style="bold magenta")
                    
                    lower_fn = name.lower()
                    idx = lower_fn.find(query)
                    if idx != -1 and query:
                        option_text.append(name[:idx], style="bold #cba6f7")
                        option_text.append(name[idx:idx+len(query)], style="bold #fab387 underline")
                        option_text.append(name[idx+len(query):], style="bold #cba6f7")
                    else:
                        option_text.append(name, style="bold #cba6f7")
                        
                    if preview:
                        option_text.append(f"  •  {preview}", style="dim #bac2de")
                else:
                    option_text.append("📁 ", style="bold yellow")
                    
                    lower_name = name.lower()
                    idx = lower_name.find(query)
                    if idx != -1 and query:
                        option_text.append(name[:idx], style="bold #cba6f7")
                        option_text.append(name[idx:idx+len(query)], style="bold #fab387 underline")
                        option_text.append(name[idx+len(query):], style="bold #cba6f7")
                    else:
                        option_text.append(name, style="bold #cba6f7")
                    
                autocomplete.add_option(Option(option_text, id=name))
            autocomplete.display = True
        else:
            autocomplete.display = False

    def _show_command_autocomplete(self, query: str) -> None:
        """Display matching slash commands in the autocomplete dropdown with rich style."""
        autocomplete = self.query_one("#mention-autocomplete", OptionList)
        autocomplete.clear_options()

        from rich.text import Text
        from textual.widgets.option_list import Option

        commands = [
            ("/settings", "⚙️", "Configure sound and desktop notification vibes"),
            ("/clear", "🧹", "Clear all chat history and reset agent"),
            ("/sync-rag", "🔄", "Incrementally sync notes with Qdrant vector DB"),
            ("/init-memory", "🧠", "Create and initialize Agent Memory.md"),
        ]
        
        matches = [cmd for cmd in commands if cmd[0].startswith("/" + query)]

        if matches:
            for cmd, icon, desc in matches:
                option_text = Text()
                option_text.append(f"{icon} ", style="bold")
                
                lower_cmd = cmd.lower()
                idx = lower_cmd.find("/" + query)
                if idx != -1 and query:
                    option_text.append(cmd[:idx], style="bold #cba6f7")
                    option_text.append(cmd[idx:idx+len(query)+1], style="bold #fab387 underline")
                    option_text.append(cmd[idx+len(query)+1:], style="bold #cba6f7")
                else:
                    option_text.append(cmd, style="bold #cba6f7")
                    
                option_text.append(f"  •  {desc}", style="dim #bac2de")
                autocomplete.add_option(Option(option_text, id=cmd))
            autocomplete.display = True
        else:
            autocomplete.display = False

    def _hide_mention_autocomplete(self) -> None:
        """Hide the mention autocomplete dropdown."""
        self.query_one("#mention-autocomplete", OptionList).display = False

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Insert selected mention or execute slash command directly."""
        if event.option.id is not None:
            self._insert_autocomplete(str(event.option.id))

    def _insert_autocomplete(self, selected_option: str) -> None:
        """Insert selected mention or execute slash command directly at the cursor."""
        chat_input = self.query_one("#chat-input", ChatInput)
        
        if selected_option.startswith("/"):
            chat_input.text = ""
            self._hide_mention_autocomplete()

            if selected_option == "/settings":
                self.app.push_screen(SettingsModal())
            elif selected_option == "/clear":
                self.clear_chat_log()
                self.app.notify("Chat log cleared")
            elif selected_option == "/sync-rag":
                self.app.run_worker(self.app._sync_rag_background())
            elif selected_option == "/init-memory":
                event = ChatInput.Submitted(chat_input, "/init-memory")
                self.on_chat_input_submitted(event)

            chat_input.focus()
            return

        cursor_row, cursor_col = chat_input.cursor_location
        lines = chat_input.text.split("\n")
        current_line = lines[cursor_row]
        
        text_before_cursor = current_line[:cursor_col]
        text_after_cursor = current_line[cursor_col:]
        
        match = re.search(r'@([^\s]*)$', text_before_cursor)
        if match:
            start_idx = match.start()
            if " " in selected_option:
                replacement = f'@"{selected_option}"'
            else:
                replacement = f"@{selected_option}"
                
            new_line = text_before_cursor[:start_idx] + replacement + " " + text_after_cursor
            lines[cursor_row] = new_line
            chat_input.text = "\n".join(lines)
            
            new_col = start_idx + len(replacement) + 1
            chat_input.cursor_location = (cursor_row, new_col)

        self._hide_mention_autocomplete()
        chat_input.focus()

    def select_active_autocomplete(self) -> None:
        """Confirm the currently highlighted autocomplete option."""
        autocomplete = self.query_one("#mention-autocomplete", OptionList)
        if autocomplete.display and autocomplete.highlighted is not None:
            option = autocomplete.get_option_at_index(autocomplete.highlighted)
            if option and option.id is not None:
                self._insert_autocomplete(str(option.id))
