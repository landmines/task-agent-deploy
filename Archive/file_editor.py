def append_to_file(filename, content):
  try:
    with open(filename, "a", encoding="utf-8") as f:
      f.write("\n" + content)
    return {"success": True, "message": f"Appended to {filename}"}
  except Exception as e:
    return {"success": False, "error": str(e)}


def replace_line(filename, target, replacement):
  try:
    with open(filename, "r", encoding="utf-8") as f:
      lines = f.readlines()

    replaced = False
    new_lines = []
    for line in lines:
      if not replaced and target in line:
        new_lines.append(replacement + "\n")
        replaced = True
      else:
        new_lines.append(line)

    with open(filename, "w", encoding="utf-8") as f:
      f.writelines(new_lines)

    if replaced:
      return {"success": True, "message": f"Replaced line in {filename}"}
    else:
      return {"success": False, "message": f"Target line not found in {filename}"}
  except Exception as e:
    return {"success": False, "error": str(e)}


def insert_below(filename, target, new_line):
  try:
    with open(filename, "r", encoding="utf-8") as f:
      lines = f.readlines()

    inserted = False
    new_lines = []
    for line in lines:
      new_lines.append(line)
      if not inserted and target in line:
        new_lines.append(new_line + "\n")
        inserted = True

    with open(filename, "w", encoding="utf-8") as f:
      f.writelines(new_lines)

    if inserted:
      return {"success": True, "message": f"Inserted line below target in {filename}"}
    else:
      return {"success": False, "message": f"Target line not found in {filename}"}
  except Exception as e:
    return {"success": False, "error": str(e)}