from pathlib import Path


def search_notes(vault_path: str, query: str) -> list[str]:
    """Search for keywords in all .md files in the Obsidian folder."""
    results = []

    EXCLUDED_DIRS = {".obsidian", ".git", ".trash", "node_modules", ".venv"}

    vault = Path(vault_path)

    for file_path in vault.rglob("*.md"):
        try:

            if any(part in EXCLUDED_DIRS for part in file_path.parts):
                continue

            content = file_path.read_text(encoding="utf-8", errors="ignore")

            if (
                query.lower() in file_path.name.lower()
                or query.lower() in content.lower()
            ):
                results.append(f"File: {file_path.name}\nIsi:\n{content[:500]}...\n")
        except OSError:
            continue

    return results


def read_note(vault_path: str, filename: str) -> str:
    """Read the full contents of a log file based on its name."""
    resolved_vault = Path(vault_path).resolve()

    matching_files = list(resolved_vault.rglob(filename))

    if not matching_files:
        return f"Error: Notes '{filename}' is not found."

    resolved_file = matching_files[0].resolve()

    if not resolved_file.is_relative_to(resolved_vault):
        return "Error: Access denied. File is outside the vault."

    try:
        return resolved_file.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return f"Error: Failed to read '{filename}' due to access rights issues."
