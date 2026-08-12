"""Settings Modal Screen — Allows configuring TUI sound and desktop notification vibes."""

import os
import re

from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Select, Switch


class SettingsModal(ModalScreen[bool]):
    """Modal screen for updating sound and notification preferences."""

    def compose(self):
        with Vertical(id="settings-container"):
            yield Label("⚙️ Application Settings", id="settings-title")

            with Horizontal(classes="settings-row"):
                yield Label("Notification Sound", classes="settings-label")
                yield Switch(id="sound-switch")

            with Horizontal(classes="settings-row"):
                yield Label("Desktop Toast Notification", classes="settings-label")
                yield Switch(id="desktop-switch")

            with Horizontal(classes="settings-row"):
                yield Label("Notification Vibe", classes="settings-label")
                yield Select(
                    options=[
                        ("🤖 Sentient (Sarcastic)", "sentient"),
                        ("☕ Coder (Relatable)", "coder"),
                        ("🚨 Dramatic (Exciting)", "dramatic"),
                        ("🏄 Surf (Chill Surfer)", "surf"),
                    ],
                    id="vibe-select",
                    allow_blank=False,
                )

            with Horizontal(id="settings-buttons"):
                yield Button("Save", variant="success", id="save-btn")
                yield Button("Cancel", id="cancel-btn")

    def on_mount(self) -> None:
        self.query_one("#settings-container").border_title = "Preferences"
        self._load_preferences()

        # Entry animations
        self.styles.animate("background", "rgba(0, 0, 0, 0.6)", duration=0.25)
        container = self.query_one("#settings-container")
        container.styles.animate("opacity", 1.0, duration=0.25, easing="out_cubic")
        container.styles.animate("offset", (0, 0), duration=0.25, easing="out_cubic")

    def dismiss_with_animation(self, result: bool) -> None:
        self.styles.animate("background", "rgba(0, 0, 0, 0.0)", duration=0.2)
        container = self.query_one("#settings-container")
        container.styles.animate("opacity", 0.0, duration=0.2, easing="in_cubic")
        container.styles.animate("offset", (0, -10), duration=0.2, easing="in_cubic",
                                 on_complete=lambda: self.dismiss(result))

    def _load_preferences(self) -> None:
        """Load settings from Agent Memory.md and apply them to widgets."""
        try:
            memory_file_path = os.path.join(
                self.app.agent.vault_path, "Agent Memory.md"
            )
            if not os.path.exists(memory_file_path):
                return

            with open(memory_file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            def get_pref(key: str, default: str) -> str:
                match = re.search(
                    rf"-\s*{re.escape(key)}\s*:\s*([^\n\r]+)", content, re.IGNORECASE
                )
                return match.group(1).strip() if match else default

            sound_pref = get_pref("Notification Sound", "enabled").lower()
            desktop_pref = get_pref("Desktop Notification", "enabled").lower()
            vibe_pref = get_pref("Notification Vibe", "sentient").lower()

            enabled_vals = ("enabled", "true", "yes", "on")

            self.query_one("#sound-switch", Switch).value = sound_pref in enabled_vals
            self.query_one("#desktop-switch", Switch).value = desktop_pref in enabled_vals
            self.query_one("#vibe-select", Select).value = vibe_pref
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle save and cancel actions with animation."""
        if event.button.id == "cancel-btn":
            self.dismiss_with_animation(False)
        elif event.button.id == "save-btn":
            self._save_preferences()

    def _save_preferences(self) -> None:
        """Save selected settings back to Agent Memory.md."""
        try:
            memory_file_path = os.path.join(
                self.app.agent.vault_path, "Agent Memory.md"
            )

            sound_val = "enabled" if self.query_one("#sound-switch", Switch).value else "disabled"
            desktop_val = "enabled" if self.query_one("#desktop-switch", Switch).value else "disabled"
            vibe_val = str(self.query_one("#vibe-select", Select).value)

            self._update_preference_in_file(memory_file_path, "Notification Sound", sound_val)
            self._update_preference_in_file(memory_file_path, "Desktop Notification", desktop_val)
            self._update_preference_in_file(memory_file_path, "Notification Vibe", vibe_val)

            self.dismiss_with_animation(True)
        except Exception:
            self.dismiss_with_animation(False)

    def _update_preference_in_file(self, file_path: str, key: str, value: str) -> None:
        """Helper to replace or append preferences in Agent Memory.md using regex."""
        if not os.path.exists(file_path):
            return

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        pattern = rf"(-\s*{re.escape(key)}\s*:\s*)([^\n\r]+)"
        if re.search(pattern, content, re.IGNORECASE):
            new_content = re.sub(
                pattern, rf"\g<1>{value}", content, flags=re.IGNORECASE
            )
        else:
            if "## ⚙️ User Preferences" in content:
                new_content = content.replace(
                    "## ⚙️ User Preferences\n",
                    f"## ⚙️ User Preferences\n- {key}: {value}\n",
                )
            else:
                new_content = f"## ⚙️ User Preferences\n- {key}: {value}\n\n" + content

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
