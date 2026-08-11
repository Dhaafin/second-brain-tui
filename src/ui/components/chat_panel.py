"""Chat Panel — Main chat interface with agent interaction, notifications, and autocomplete."""

import asyncio
import os
import random
import re

from textual.containers import Vertical
from textual.widgets import Input, Label, Markdown, OptionList


class FocusableMarkdown(Markdown):
    """Markdown widget that can accept keyboard focus for scrolling."""

    can_focus = True


class ChatInput(Input):
    """Custom Input with standard selection and cursor bindings."""

    BINDINGS = (
        ("ctrl+a", "select_all", "Select All"),
        ("ctrl+home", "home(True)", "Select to Start"),
        ("ctrl+end", "end(True)", "Select to End"),
    )


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


class ChatPanel(Vertical):
    """Main chat panel handling user input, agent responses, and notifications."""

    def compose(self):
        yield FocusableMarkdown(id="chat-log")
        yield Label("", id="loading-status")
        yield OptionList(id="mention-autocomplete")
        yield ChatInput(
            placeholder="Type a message to Agnes...", id="chat-input"
        )

    def on_mount(self) -> None:
        self.query_one("#mention-autocomplete").display = False
        self.chat_history: list[str] = [WELCOME_MESSAGE]

        # Surf animation state
        self.surf_pos = 0
        self.surf_dir = 1
        self.surf_width = 30
        self.wave_offset = 0
        self.wave_chars = "~≈∽≈"
        self.elapsed_time = 0.0
        self.current_agent_status = "is thinking"

        chat_log = self.query_one("#chat-log", Markdown)
        chat_log.update("\n\n".join(self.chat_history))

    def scroll_chat_to_bottom(self, chat_log: Markdown) -> None:
        """Scroll the chat log to the very bottom."""
        chat_log.scroll_end(animate=False)

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

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle user message submission."""
        user_text = event.value.strip()
        if not user_text:
            return

        chat_log = self.query_one("#chat-log", Markdown)
        chat_input = self.query_one("#chat-input", Input)
        loading_status = self.query_one("#loading-status", Label)

        # Append user message and update display
        chat_input.disabled = True
        self.chat_history.append(f"### You\n{user_text}")
        chat_log.update("\n\n".join(self.chat_history))
        chat_input.value = ""
        self.call_after_refresh(self.scroll_chat_to_bottom, chat_log)

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

            # Append agent response and scroll
            self.chat_history.append(f"### Agent\n{response}")
            chat_log.update("\n\n".join(self.chat_history))
            self.call_after_refresh(self.scroll_chat_to_bottom, chat_log)

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

    def on_input_changed(self, event: Input.Changed) -> None:
        """Show mention autocomplete when user types @."""
        value = event.value
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
        chat_input = self.query_one("#chat-input", Input)

        value = chat_input.value
        parts = value.split(" ")

        if " " in selected_option:
            replacement = f'@"{selected_option}"'
        else:
            replacement = f"@{selected_option}"

        parts[-1] = replacement
        chat_input.value = " ".join(parts) + " "

        self._hide_mention_autocomplete()
        chat_input.focus()

    def on_key(self, event) -> None:
        """Navigate to autocomplete dropdown with arrow key."""
        if event.key == "down" and self.query_one("#mention-autocomplete").display:
            self.query_one("#mention-autocomplete").focus()
