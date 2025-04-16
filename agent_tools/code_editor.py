import os
from datetime import datetime, UTC

def insert_code_after_line_in_function(filename, function_name, anchor_line, new_code_block):
    with open(filename, "r", encoding="utf-8") as f:
        lines = f.readlines()

    in_function = False
    indent = ""
    inserted = False
    new_lines = []
    backup_path = f"{filename}.bak.{datetime.now(UTC).isoformat().replace(':', '_')}"

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("def ") and function_name in stripped:
            in_function = True
            indent = line[:len(line) - len(line.lstrip())]

        new_lines.append(line)

        if in_function and anchor_line.strip() in stripped and not inserted:
            # Insert after this line
            for new_code_line in new_code_block.splitlines():
                new_lines.append(indent + "    " + new_code_line + "\n")
            inserted = True

        # Exit block if indentation level drops
        if in_function and not line.startswith(indent) and not line.strip() == "":
            in_function = False

    if not inserted:
        return {"success": False, "error": f"Anchor line not found in {function_name}."}

    # Write backup and save new file
    with open(backup_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    with open(filename, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    return {
        "success": True,
        "message": f"Inserted code into {filename} after '{anchor_line}' inside {function_name}()",
        "backup_path": backup_path,
        "lines_inserted": len(new_code_block.splitlines())
    }
