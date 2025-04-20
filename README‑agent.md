# Agent CLI Quickstart

This is a tiny wrapper around your Builder‑Agent HTTP API that hides all the JSON boilerplate and pretty‑prints results.

---

## 1. Install dependencies

You need Python 3 and pip. Then:

```bash
pip install click requests
```

---

## 2. Make the CLI executable

From your project root:

```bash
chmod +x agent
```

---

## 3. Usage

All commands follow the pattern:

```bash
./agent <command> [OPTIONS] ARGS…
```

Below are the most common ones:

### create‑file

Create a new file with CONTENT:

```bash
./agent create-file <filename> "<content>"
```

**Example:**

```bash
./agent create-file notes.txt "First line\nSecond line\n"
```

---

### append‑to‑file

Append CONTENT to an existing file:

```bash
./agent append-to-file <filename> "<content>"
```

**Example:**

```bash
./agent append-to-file notes.txt "Another line\n"
```

---

### insert‑below

Insert NEW_LINE immediately after the first line matching TARGET:

```bash
./agent insert-below <filename> "<target>" "<new_line>"
```

**Example:**

```bash
./agent insert-below notes.txt "First line" "Inserted after first"
```

---

### replace‑line

Replace the first line containing TARGET with REPLACEMENT.  
Use `--self-modify` if you need to edit core agent files:

```bash
./agent replace-line <filename> "<target>" "<replacement>" [--self-modify]
```

**Example (user files):**

```bash
./agent replace-line notes.txt "Inserted after first" "New text"
```

**Example (core file):**

```bash
./agent replace-line file_ops.py "def insert_below" "def insert_below_patched" --self-modify
```

---

### patch‑code

Insert NEW_CODE immediately after the first line matching AFTER_LINE:

```bash
./agent patch-code <filename> "<after_line>" "<new_code>"
```

**Example:**

```bash
./agent patch-code demo_code.py "def greet(name):" "    print('[PATCHED]')"
```

---

### modify‑file

Replace the first occurrence of OLD_CONTENT with NEW_CONTENT:

```bash
./agent modify-file <filename> "<old_content>" "<new_content>"
```

---

### delete‑file

Delete a file from disk:

```bash
./agent delete-file <filename>
```

---

### run‑next

Pop and run the next queued task:

```bash
./agent run-next
```

---

### latest

Fetch the most recent log entry:

```bash
./agent latest
```

---

### confirm

Approve or reject a pending task by its log ID:

```bash
./agent confirm <task_id> [--yes | --no]
```

Default is `--yes`.

**Example:**

```bash
./agent confirm 20250420_192553 --yes
```

---

## 4. Optional tips

- **Tab completion** (bash or zsh):

  ```bash
  # in ~/.bashrc or ~/.zshrc
  eval "$(_AGENT_COMPLETE=source_bash agent)"
  ```

- **Error handling**:  
  If the agent is down or returns non‑JSON, you’ll see a Python error—consider wrapping `_call()` in try/except.

- **Verbose mode**:  
  You could add a global `--verbose` flag to dump the full wrapper response.
