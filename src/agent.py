import json
import logging
import os
import re
from pathlib import Path

from openai import OpenAI

from src.rag import (
    delete_directory_index,
    delete_file_index,
    index_file,
    query_semantic_notes,
)
from src.vault import (
    append_note,
    delete_directory_to_trash,
    delete_to_trash,
    generate_vault_index,
    list_vault_directory,
    read_note,
    restore_from_trash,
    update_vault_index_in_memory,
    write_note,
)

from dotenv import load_dotenv

load_dotenv(".env.local")


client = OpenAI(api_key=os.getenv("AI_API_KEY"), base_url=os.getenv("AI_BASE_URL"))

AI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_notes",
            "description": "Search for keywords in all .md files in the Obsidian vault.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search keyword."}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_note",
            "description": "Read the full contents of a note by its filename.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "The filename, e.g., 'Idea.md'.",
                    }
                },
                "required": ["filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_note",
            "description": "Create a new note or overwrite an existing note in the vault with structured markdown content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "The target relative path and filename, e.g., 'Notes/Draft.md'.",
                    },
                    "content": {
                        "type": "string",
                        "description": "The markdown content of the note.",
                    },
                },
                "required": ["filename", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "append_note",
            "description": "Append text or logs to the bottom of an existing note in the vault.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "The target filename, e.g., 'DailyLog.md'.",
                    },
                    "content": {
                        "type": "string",
                        "description": "The text content to append.",
                    },
                },
                "required": ["filename", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_to_trash",
            "description": "Delete a note and send it to a trash",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "The filename, e.g., 'Idea.md'.",
                    }
                },
                "required": ["filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "restore_from_trash",
            "description": "Restore a deleted items from the trash",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "The filename, e.g., 'Idea.md'.",
                    }
                },
                "required": ["filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_vault_directory",
            "description": "List all active folder paths in the user's vault to inspect the directory structure before writing notes.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_directory",
            "description": "Delete a folder/directory and all its contents by moving it to the trash.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dir_path": {
                        "type": "string",
                        "description": "The relative directory path, e.g., '03 Resources/Literasi Digital'.",
                    }
                },
                "required": ["dir_path"],
            },
        },
    },
]


class SecondBrainAgent:
    def __init__(self):
        """Lightweight init — zero I/O. Call load_memory() separately after TUI renders."""
        self.vault_path = os.getenv("OBSIDIAN_PATH")
        self.model = os.getenv("AI_MODEL")
        self.max_steps = int(os.getenv("AI_MAX_STEPS", "10"))

        self.system_prompt = (
            "You are a Second Brain AI Agent. You have access to the user's personal Obsidian notes.\n\n"
            "CRITICAL RULES:\n"
            "1. ALWAYS search for notes first using `search_notes` before answering any question about the user's thoughts, plans, files, or ideas. Do NOT assume or guess.\n"
            "2. If you find relevant files in the search results, you MUST call `read_note` to read their full content before formulating your summary or answer.\n"
            "3. Never say a note does not exist without searching for it first.\n"
            "4. If the user asks you to write or edit notes, check if similar notes exist first to maintain connections.\n"
            "5. Be concise and base your answers strictly on the retrieved note contents whenever possible."
            "6. PARALLEL TOOL CALLS: If you need to read multiple notes, call `read_note` for ALL of them in a single turn. Do NOT call them one by one in sequence.\n"
            "7. SEARCH PREVIEWS: The `search_notes` tool returns the first 500 characters of each note. If this preview content is already sufficient to answer the user's question, answer immediately. Only call `read_note` if you need the full content."
            "8. FOLDER NAVIGATION: If you need to create a new note or folder but are unsure which directory to use, call `list_vault_directory` to inspect the user's existing vault structure first. Always try to match the user's folder pattern.\n"
            "9. PERSISTENT MEMORY: You have a persistent memory note named `Agent Memory.md`. If the user gives you instructions, folder preferences, active project mappings, or goals to remember across sessions, write or append them to `Agent Memory.md` using `write_note` or `append_note` so they persist."
        )
        self.messages = [{"role": "system", "content": self.system_prompt}]
        self.awaiting_onboarding_consent = False
        self._memory_loaded = False

    def load_memory(self, update_index: bool = False) -> None:
        """Read persistent memory from Agent Memory.md and inject it into the chat history."""
        if update_index:
            update_vault_index_in_memory(self.vault_path)

        memory_content = read_note(self.vault_path, "Agent Memory.md")

        if not memory_content.startswith("Error:"):
            # Remove any previous memory system message before appending fresh one
            self.messages = [
                m for m in self.messages
                if not (m.get("role") == "system" and "persistent memory" in m.get("content", "").lower())
            ]
            self.messages.append(
                {
                    "role": "system",
                    "content": f"Here is your persistent memory from the previous session (containing user preferences, active projects, and folder rules):\n\n{memory_content}",
                }
            )
        self._memory_loaded = True

    def process_onboarding(self, user_response: str) -> str:
        """Process the user's response to the onboarding question for Agent Memory initialization."""
        cleaned = user_response.lower().strip()
        if cleaned in ("yes", "ya", "y", "setuju", "agree", "boleh", "ok", "okay"):
            self.awaiting_onboarding_consent = False
            default_template = (
                "# Agent Memory\n\n"
                "File ini digunakan oleh Second Brain AI Agent untuk menyimpan preferensi, "
                "aturan folder, dan informasi penting lintas sesi. Anda dapat mengedit file ini secara manual langsung di Obsidian.\n\n"
                "## ⚙️ User Preferences\n"
                "- Language: Indonesian\n"
                "- Default Project Directory: 01 Projects\n"
                "- Default Capture Directory: 00 Inbox\n"
                "- Notification Sound: enabled\n"
                "- Desktop Notification: enabled\n"
                "- Notification Vibe: Sentient\n\n"
                "## 🧠 Custom Rules\n"
                "- Selalu gunakan tool `list_vault_directory` sebelum membuat folder atau menulis catatan baru.\n"
                "- Prefer to reply in Indonesian unless requested otherwise.\n\n"
                "<!-- MAP_START -->\n"
                f"{generate_vault_index(self.vault_path)}\n"
                "<!-- MAP_END -->"
            )
            write_note(self.vault_path, "Agent Memory.md", default_template)
            self.load_memory()
            return (
                "Awesome! Saya sudah menginisialisasi berkas `Agent Memory.md` di root vault Anda. "
                "Memori persisten Anda sekarang aktif dan telah saya muat. Ada yang bisa saya bantu hari ini?"
            )
        elif cleaned in ("no", "tidak", "ga", "gak", "n", "disagree", "jangan"):
            self.awaiting_onboarding_consent = False
            return (
                "Baiklah. Saya akan berjalan tanpa memori persisten untuk sesi ini. "
                "Jika Anda berubah pikiran, Anda bisa membuat berkas `Agent Memory.md` secara manual "
                "atau mengetik `/init-memory` untuk membuatnya nanti. Ada yang bisa saya bantu?"
            )
        else:
            return (
                "Saya kurang mengerti jawaban Anda. Apakah Anda setuju jika saya membuat file `Agent Memory.md` "
                "di root vault Anda? (Ketik **ya** atau **tidak**)"
            )

    def parse_file_mentions(self, prompt: str) -> tuple[str, str]:
        """Detect and load file or folder content mentioned via @filename or @'filename'"""
        pattern = r'@(?:"([^"]+)"|(\S+))'
        matches = re.findall(pattern, prompt)

        contexts = []
        clean_prompt = prompt

        for match in matches:
            filename = match[0] if match[0] else match[1]
            
            # Check if it is a directory path
            dir_path = (Path(self.vault_path) / filename).resolve()
            if dir_path.is_dir() and dir_path.is_relative_to(Path(self.vault_path).resolve()):
                EXCLUDED_DIRS = {".obsidian", ".git", ".trash", "node_modules", ".venv", "__pycache__"}
                files_in_dir = []
                for p in dir_path.rglob("*.md"):
                    if any(part in EXCLUDED_DIRS for part in p.parts):
                        continue
                    rel_p = p.relative_to(Path(self.vault_path).resolve())
                    files_in_dir.append(str(rel_p).replace("\\", "/"))
                
                content = "Folder directory list:\n" + "\n".join(f"- {f}" for f in sorted(files_in_dir))
                contexts.append(f"=== DIRECTORY LIST OF FOLDER {filename} ===\n{content}\n")
                clean_prompt = clean_prompt.replace(f"@{filename}", "").replace(
                    f'@"{filename}"', ""
                )
                continue

            # Fallback to note file parsing
            orig_filename = filename
            if not filename.endswith(".md"):
                filename += ".md"

            content = read_note(self.vault_path, filename)
            if not content.startswith("Error:"):
                contexts.append(f"=== CONTENT OF {filename} ===\n{content}\n")
                clean_prompt = clean_prompt.replace(f"@{orig_filename}", "").replace(
                    f'@"{orig_filename}"', ""
                )

        return clean_prompt.strip(), "\n".join(contexts)

    def clear_history(self) -> None:
        """Reset conversation history — no I/O, instant."""
        self.messages = [{"role": "system", "content": self.system_prompt}]
        self.awaiting_onboarding_consent = False
        # Re-inject cached memory if available (no disk I/O)
        if self._memory_loaded:
            memory_content = read_note(self.vault_path, "Agent Memory.md")
            if not memory_content.startswith("Error:"):
                self.messages.append(
                    {
                        "role": "system",
                        "content": f"Here is your persistent memory from the previous session (containing user preferences, active projects, and folder rules):\n\n{memory_content}",
                    }
                )

    def ask(self, user_message: str, on_status_update=None) -> str:
        """Send a message to the AI and run the tool call loop if necessary"""
        if user_message.strip().lower() == "/init-memory":
            self.awaiting_onboarding_consent = False
            default_template = (
                "# Agent Memory\n\n"
                "File ini digunakan oleh Second Brain AI Agent untuk menyimpan preferensi, "
                "aturan folder, dan informasi penting lintas sesi. Anda dapat mengedit file ini secara manual langsung di Obsidian.\n\n"
                "## ⚙️ User Preferences\n"
                "- Language: Indonesian\n"
                "- Default Project Directory: 01 Projects\n"
                "- Default Capture Directory: 00 Inbox\n"
                "- Notification Sound: enabled\n"
                "- Desktop Notification: enabled\n"
                "- Notification Vibe: Sentient\n\n"
                "## 🧠 Custom Rules\n"
                "- Selalu gunakan tool `list_vault_directory` sebelum membuat folder atau menulis catatan baru.\n"
                "- Prefer to reply in Indonesian unless requested otherwise.\n\n"
                "<!-- MAP_START -->\n"
                f"{generate_vault_index(self.vault_path)}\n"
                "<!-- MAP_END -->"
            )
            write_note(self.vault_path, "Agent Memory.md", default_template)
            self.load_memory()
            return "Berkas `Agent Memory.md` berhasil diinisialisasi secara manual di root vault Anda!"

        # Parse file mentions in user prompt
        clean_message, context = self.parse_file_mentions(user_message)
        if context:
            user_message_to_send = f"{clean_message}\n\n{context}"
        else:
            user_message_to_send = user_message

        self.messages.append({"role": "user", "content": user_message_to_send})
        logging.getLogger("second_brain").info("User query: %s", user_message_to_send)

        for step in range(self.max_steps):
            steps_remaining = self.max_steps - step
            logging.getLogger("second_brain").info(
                "Step %d of %d starting. Requesting LLM completion.", step + 1, self.max_steps
            )
            step_notice = (
                f"[SYSTEM NOTICE: You are at step {step + 1} of {self.max_steps}. "
                f"You have {steps_remaining} steps remaining in this turn to complete all your tasks. "
                "If you need to perform many actions, use batch tools (like delete_directory) if available, "
                "or complete what you can and ask the user to confirm to continue in the next turn.]"
            )
            api_messages = [{"role": "system", "content": step_notice}] + self.messages

            response = client.chat.completions.create(
                model=self.model,
                messages=api_messages,
                tools=AI_TOOLS,
                tool_choice="auto",
            )

            response_message = response.choices[0].message
            logging.getLogger("second_brain").info(
                "LLM response: content='%s', tool_calls=%s",
                response_message.content,
                [tc.function.name for tc in response_message.tool_calls] if response_message.tool_calls else None
            )

            # Convert response message to a clean dictionary to remove non-standard/extra fields (like reasoning_content)
            # that cause API gateways to reject the request body with a 400 Bad Request error.
            clean_message = {"role": "assistant"}
            if response_message.content is not None:
                clean_message["content"] = response_message.content
            if response_message.tool_calls:
                clean_message["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in response_message.tool_calls
                ]
            self.messages.append(clean_message)

            if not response_message.tool_calls:
                return response_message.content or "No response from AI."

            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                logging.getLogger("second_brain").info(
                    "Executing tool: name='%s', args=%s", function_name, function_args
                )

                if function_name == "list_vault_directory":
                    if on_status_update:
                        on_status_update("listing vault directories")
                    dirs = list_vault_directory(self.vault_path)
                    tool_output = "\n".join(dirs) if dirs else "No directories found"

                elif function_name == "search_notes":
                    query = function_args.get("query")
                    if on_status_update:
                        on_status_update(f"searching notes for '{query}'")
                    semantic_hits = query_semantic_notes(query, limit=5)
                    results = []
                    for hit in semantic_hits:
                        filename = hit.payload.get("filename", "unknown")
                        text = hit.payload.get("text", "")
                        score = hit.score
                        results.append(
                            f"=== File: '{filename}' (Similarity: {score:.4f}) ===\n"
                            f"Content Snippet:\n{text}\n"
                        )
                    tool_output = "\n".join(results) if results else "No semantic matches found."

                elif function_name == "delete_to_trash":
                    filename = function_args.get("filename")
                    if on_status_update:
                        on_status_update(f"deleting '{filename}' to trash")
                    tool_output = delete_to_trash(self.vault_path, filename)
                    if not tool_output.startswith("Error"):
                        delete_file_index(filename)

                elif function_name == "delete_directory":
                    dir_path = function_args.get("dir_path")
                    if on_status_update:
                        on_status_update(f"deleting folder '{dir_path}' to trash")
                    tool_output = delete_directory_to_trash(self.vault_path, dir_path)
                    if not tool_output.startswith("Error"):
                        delete_directory_index(dir_path)

                elif function_name == "restore_from_trash":
                    filename = function_args.get("filename")
                    if on_status_update:
                        on_status_update(f"restoring '{filename}' from trash")
                    tool_output = restore_from_trash(self.vault_path, filename)
                    if not tool_output.startswith("Error"):
                        index_file(self.vault_path, filename)

                elif function_name == "read_note":
                    filename = function_args.get("filename")
                    if on_status_update:
                        on_status_update(f"reading note '{filename}'")
                    tool_output = read_note(self.vault_path, filename)

                elif function_name == "write_note":
                    filename = function_args.get("filename")
                    content = function_args.get("content")
                    if on_status_update:
                        on_status_update(f"writing note '{filename}'")
                    tool_output = write_note(self.vault_path, filename, content)
                    if not tool_output.startswith("Error"):
                        index_file(self.vault_path, filename)

                elif function_name == "append_note":
                    filename = function_args.get("filename")
                    content = function_args.get("content")
                    if on_status_update:
                        on_status_update(f"appending to '{filename}'")
                    tool_output = append_note(self.vault_path, filename, content)
                    if not tool_output.startswith("Error"):
                        index_file(self.vault_path, filename)

                else:
                    tool_output = f"Error: Tool '{function_name}' not found."
                logging.getLogger("second_brain").info(
                    "Tool '%s' returned: %s", function_name, tool_output
                )
                self.messages.append(
                    {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": tool_output,
                    }
                )

        logging.getLogger("second_brain").error("Agent reasoning budget exhausted.")
        return "Error: Agent reached maximum reasoning steps without answering."
