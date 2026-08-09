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

def write_note(base_dir_str : str, rel_path_str: str, text: str) -> str:
    base_dir = Path(base_dir_str).resolve()

    target_file= (base_dir / rel_path_str).resolve()

    if not target_file.is_relative_to(base_dir):
        return "Error: Access denied. Target path is outside the sandbox"

    try:
        target_file.parent.mkdir(parents=True, exist_ok=True)
        
        target_file.write_text(text, encoding="utf-8")

        return f"Success: Note '{rel_path_str}' has been saved."
    except OSError:
        return f"Error: Failed to write '{rel_path_str}' due to access issues."

def append_note(base_dir_str: str, rel_path_str:str, text:str) -> str:
    base_dir =Path(base_dir_str).resolve()
    target_file = (base_dir/rel_path_str).resolve()

    if not target_file.is_relative_to(base_dir):
        return "Error: Access denied. Target path is outside the sandbox"

    try:
        target_file.parent.mkdir(parents=True, exist_ok=True)

        with open(target_file, "a", encoding="utf-8") as f:
            f.write ("\n" + text)
            
        return f"Success: Content Appended to '{rel_path_str}'"
    except OSError:
        return f"Error: Failed to append to '{rel_path_str}' due to access"
         
def delete_to_trash(vault_path:str, filename:str) -> str:
    resolved_vault = Path(vault_path).resolve()
    src_path = (resolved_vault / filename).resolve()

    dest_path = (resolved_vault / ".trash" / filename).resolve()

    if not src_path.is_relative_to(resolved_vault) or src_path == resolved_vault:
        return "Error : Access denied. Cannot delete files outside of the vault"

    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        import shutil
        shutil.move(str(src_path), str(dest_path))
        return f"Success: Moved '{filename}' to trash"
    except OSError as e:
        return f"Error: failed to move '{filename}' to trash due to access issues"
            

    
