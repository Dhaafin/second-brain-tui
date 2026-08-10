import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from src.vault import append_note, read_note, write_note, search_notes, delete_to_trash, restore_from_trash, list_vault_directory

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
                        "description": "The target relative path and filename, e.g., 'Notes/Draft.md'."
                    },
                    "content": {
                        "type": "string",
                        "description": "The markdown content of the note."
                    }
                },
                "required": ["filename", "content"]
            }
        }
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
                        "description": "The target filename, e.g., 'DailyLog.md'."
                    },
                    "content": {
                        "type": "string",
                        "description": "The text content to append."
                    }
                },
                "required": ["filename", "content"]
            }
        }
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
]


class SecondBrainAgent:
    def __init__(self):
        self.vault_path = os.getenv("OBSIDIAN_PATH")
        self.model = os.getenv("AI_MODEL")

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
        self.messages = [
            {"role": "system", "content": self.system_prompt}
        ]
        self.load_memory()
        
    def load_memory(self) -> None:
        """Read persistent memory from Agent Memory.md and inject it into the chat history."""

        memory_content = read_note(self.vault_path, "Agent Memory.md")

        if not memory_content.startswith("Error:"):
            self.messages.append({
                "role": "system",
                "content" : f"Here is your persistent memory from the previous session (containing user preferences, active projects, and folder rules):\n\n{memory_content}"
            })

    def clear_history(self) -> None:
        """Reset conversation history back to only the system prompt."""
        self.messages = [
            {"role": "system", "content": self.system_prompt}
        ]
        self.load_memory()

    def ask(self, user_message: str, on_status_update=None) -> str:
        """Send a message to the AI and run the tool call loop if necessary"""

        self.messages.append({"role": "user","content": user_message})

        for _ in range(5):
            response = client.chat.completions.create(
                model=self.model, messages=self.messages, tools=AI_TOOLS, tool_choice="auto"
            )

            response_message = response.choices[0].message

            # Convert response message to a clean dictionary to remove non-standard/extra fields (like reasoning_content)
            # that cause API gateways to reject the request body with a 400 Bad Request error.
            clean_message = {
                "role": "assistant"
            }
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
                        }
                    }
                    for tc in response_message.tool_calls
                ]
            self.messages.append(clean_message)

            if not response_message.tool_calls:
                return response_message.content or "No response from AI."

            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name

                function_args = json.loads(tool_call.function.arguments)

                if function_name == "list_vault_directory":
                    if on_status_update:
                        on_status_update("listing vault directories")
                    dirs = list_vault_directory(self.vault_path)
                    tool_output = "\n".join(dirs) if dirs else "No directories found"

                elif function_name == "search_notes":
                    query = function_args.get("query")
                    if on_status_update:
                        on_status_update(f"searching notes for '{query}'")
                    search_results = search_notes(self.vault_path, query)
                    tool_output = (
                        "\n".join(search_results)
                        if search_results
                        else "No Notes Found"
                    )

                elif function_name == "delete_to_trash":
                    filename =function_args.get("filename")
                    if on_status_update:
                        on_status_update(f"deleting '{filename}' to trash")
                    tool_output = delete_to_trash(self.vault_path, filename)

                elif function_name == "restore_from_trash":
                    filename =function_args.get("filename")
                    if on_status_update:
                        on_status_update(f"restoring '{filename}' from trash")
                    tool_output = restore_from_trash(self.vault_path, filename)

                elif function_name == "read_note":
                    filename = function_args.get("filename")
                    if on_status_update:
                        on_status_update(f"reading note '{filename}'")
                    tool_output = read_note(self.vault_path, filename)

                elif function_name == "write_note":
                    filename = function_args.get("filename")
                    content = function_args.get ("content")
                    if on_status_update:
                        on_status_update(f"writing note '{filename}'")
                    tool_output = write_note(self.vault_path, filename, content)

                elif function_name == "append_note":
                    filename = function_args.get("filename")
                    content = function_args.get ("content")
                    if on_status_update:
                        on_status_update(f"appending to '{filename}'")
                    tool_output = append_note(self.vault_path, filename, content)

                else:
                    tool_output = f"Error: Tool '{function_name}' not found."
                self.messages.append(
                    {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": tool_output,
                    }
                )

        return "Error: Agent reached maximum reasoning steps without answering."