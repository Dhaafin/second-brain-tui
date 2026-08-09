import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from src.vault import append_note, read_note, write_note, search_notes, delete_to_trash, restore_from_trash

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

        )
        self.messages = [
            {"role": "system", "content": self.system_prompt}
        ]
        
    def clear_history(self) -> None:
        """Reset conversation history back to only the system prompt."""
        self.messages = [
            {"role": "system", "content": self.system_prompt}
        ]


    def ask(self, user_message: str) -> str:
        """Send a message to the AI and run the tool call loop if necessary"""

        self.messages.append({"role": "user","content": user_message})

        for _ in range(5):
            response = client.chat.completions.create(
                model=self.model, messages=self.messages, tools=AI_TOOLS, tool_choice="auto"
            )

            response_message = response.choices[0].message

            self.messages.append(response_message)

            if not response_message.tool_calls:
                return response_message.content or "No response from AI."

            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name

                function_args = json.loads(tool_call.function.arguments)

                if function_name == "search_notes":
                    query = function_args.get("query")
                    search_results = search_notes(self.vault_path, query)
                    tool_output = (
                        "\n".join(search_results)
                        if search_results
                        else "No Notes Found"
                    )

                elif function_name == "delete_to_trash":
                    filename =function_args.get("filename")
                    tool_output = delete_to_trash(self.vault_path, filename)

                elif function_name == "restore_from_trash":
                    filename =function_args.get("filename")
                    tool_output = restore_from_trash(self.vault_path, filename)

                elif function_name == "read_note":
                    filename = function_args.get("filename")
                    tool_output = read_note(self.vault_path, filename)

                elif function_name == "write_note":
                    filename = function_args.get("filename")
                    content = function_args.get ("content")
                    tool_output = write_note(self.vault_path, filename, content)

                elif function_name == "append_note":
                    filename = function_args.get("filename")
                    content = function_args.get ("content")
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
