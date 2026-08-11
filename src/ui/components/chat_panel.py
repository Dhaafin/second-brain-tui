"""Chat Panel — Main chat interface with agent interaction, notifications, and autocomplete."""

from textual.message import Message
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Label, Markdown, OptionList, TextArea


import asyncio
import os
import random
import re

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
        if event.key in ("ctrl+j", "ctrl+enter", "ctrl+s"):
            event.prevent_default()
            text_value = self.text.strip()
            if text_value:
                self.post_message(self.Submitted(self.text))

    def action_open_editor(self) -> None:
        """Open system default text editor (Notepad on Windows) to edit long prompts."""
        import tempfile
        import subprocess

        temp_fd, temp_path = tempfile.mkstemp(suffix=".md", prefix="sb_prompt_")
        try:
            os.write(temp_fd, self.text.encode("utf-8"))
            os.close(temp_fd)

            with self.app.suspend():
                subprocess.run(["notepad.exe", temp_path])

            with open(temp_path, "r", encoding="utf-8", errors="ignore") as f:
                new_text = f.read()

            self.text = new_text
            self.move_cursor((len(new_text.split("\n")) - 1, len(new_text.split("\n")[-1])))
        except Exception:
            pass
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                pass


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

    def __init__(self, sender: str, text: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.sender = sender
        self.text = text

    def compose(self):
        if self.sender == "You":
            yield Label("👤 You", classes="chat-bubble-header user-header")
            yield Markdown(self.text, classes="chat-bubble-content user-content")
        else:
            yield Label("🏄 Agnes", classes="chat-bubble-header agent-header")
            yield Markdown(self.text, classes="chat-bubble-content agent-content")


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

        # Surf animation state
        self.surf_pos = 0
        self.surf_dir = 1
        self.surf_width = 30
        self.wave_offset = 0
        self.wave_chars = "~≈∽≈"
        self.elapsed_time = 0.0
        self.current_agent_status = "is thinking"

        # Mount initial welcome message
        container = self.query_one("#chat-log-container", VerticalScroll)
        container.mount(
            ChatMessage(sender="Agent", text=WELCOME_MESSAGE, classes="chat-message chat-message-agent")
        )

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
        container.mount(ChatMessage(sender=sender, text=text, classes=classes))
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
        except Exception:
            pass

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
            container = self.query_one("#chat-log-container", VerticalScroll)
            container.mount(
                ChatMessage(sender="Agent", text=response, classes="chat-message chat-message-agent")
            )
            self.call_after_refresh(self.scroll_chat_to_bottom, container)

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
        except Exception:
            pass

    # --- Mention Autocomplete ---

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """Show mention autocomplete when user types @ and adjust height dynamically."""
        value = event.text_area.text

        # Auto-grow input box height dynamically (min 3, max 8 rows)
        num_lines = len(value.split("\n"))
        event.text_area.styles.height = min(max(3, num_lines + 2), 8)

        if "@" in value:
            parts = value.split(" ")
            last_part = parts[-1]
            if last_part.startswith("@"):
                query = last_part[1:].lower()
                self._show_mention_autocomplete(query)
                return
        self._hide_mention_autocomplete()

    def _show_mention_autocomplete(self, query: str) -> None:
        """Display matching note filenames in the autocomplete dropdown."""
        autocomplete = self.query_one("#mention-autocomplete", OptionList)
        autocomplete.clear_options()

        from src.vault import get_all_note_paths

        all_paths = get_all_note_paths(self.app.agent.vault_path)
        matches = [
            os.path.basename(p)
            for p in all_paths
            if query in os.path.basename(p).lower()
        ][:5]

        if matches:
            for match in matches:
                autocomplete.add_option(match)
            autocomplete.display = True
        else:
            autocomplete.display = False

    def _hide_mention_autocomplete(self) -> None:
        """Hide the mention autocomplete dropdown."""
        self.query_one("#mention-autocomplete", OptionList).display = False

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Insert selected mention into the chat input."""
        selected_option = event.option.prompt
        chat_input = self.query_one("#chat-input", TextArea)

        value = chat_input.text
        parts = value.split(" ")

        if " " in selected_option:
            replacement = f'@"{selected_option}"'
        else:
            replacement = f"@{selected_option}"

        parts[-1] = replacement
        chat_input.text = " ".join(parts) + " "

        self._hide_mention_autocomplete()
        chat_input.focus()

    def on_key(self, event) -> None:
        """Navigate to autocomplete dropdown with arrow key."""
        if event.key == "down" and self.query_one("#mention-autocomplete").display:
            self.query_one("#mention-autocomplete").focus()
