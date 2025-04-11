from context_manager import load_memory, add_next_step, save_memory

ctx = load_memory()

task = {
    "intent": "create_file",
    "filename": "queued_test_file.txt",
    "content": "✅ Queued by /run_next test"
}

add_next_step(ctx, task)
save_memory(ctx)

print("✅ Task queued. Current queue:")
print(ctx.get("next_steps", []))