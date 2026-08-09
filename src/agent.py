import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from src.vault import read_note, search_notes

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
]


class SecondBrainAgent:
    def __init__(self):
        self.vault_path = os.getenv("OBSIDIAN_PATH")
        self.model = os.getenv("AI_MODEL")

        self.system_prompt = (
            "You are a Second Brain AI Agent. Help the user analyze their personal notes. "
            "Use the provided tools to search and read their notes before answering."
        )

    def ask(self, user_message: str) -> str:
        """Send a message to the AI and run the tool call loop if necessary"""

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_message},
        ]

        for _ in range(5):
            response = client.chat.completions.create(
                model=self.model, messages=messages, tools=AI_TOOLS, tool_choice="auto"
            )

            response_message = response.choices[0].message

            messages.append(response_message)

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

                elif function_name == "read_note":
                    filename = function_args.get("filename")
                    tool_output = read_note(self.vault_path, filename)

                else:
                    tool_output = f"Error: Tool '{function_name}' tidak ditemukan."
                messages.append(
                    {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": tool_output,
                    }
                )

        return "Error: Agent reached maximum reasoning steps without answering."
