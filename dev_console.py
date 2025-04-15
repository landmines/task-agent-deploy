import sys
import os

def create_file(filename, content):
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ File created: {filename}")

def append_to_file(filename, content):
    with open(filename, "a", encoding="utf-8") as f:
        f.write("\n" + content)
    print(f"✅ Content appended to: {filename}")

def read_file(filename):
    if not os.path.exists(filename):
        print("❌ File not found.")
        return
    with open(filename, "r", encoding="utf-8") as f:
        print(f"📄 Contents of {filename}:\n")
        print(f.read())

def delete_file(filename):
    if not os.path.exists(filename):
        print("❌ File does not exist.")
        return
    os.remove(filename)
    print(f"🗑️ File deleted: {filename}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage:")
        print("  python dev_console.py create_file filename content")
        print("  python dev_console.py append_to_file filename content")
        print("  python dev_console.py read_file filename")
        print("  python dev_console.py delete_file filename")
        sys.exit(1)

    action = sys.argv[1]
    filename = sys.argv[2]
    content = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else None

    if action == "create_file":
        create_file(filename, content)
    elif action == "append_to_file":
        append_to_file(filename, content)
    elif action == "read_file":
        read_file(filename)
    elif action == "delete_file":
        delete_file(filename)
    else:
        print("❌ Unknown action.")