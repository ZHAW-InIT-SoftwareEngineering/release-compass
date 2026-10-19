# HITL implementation steps

The intended flow is:

```text
LLM ─ ordinary tool call ─> tools ─> LLM
  └─ cicd_tool call ─> approval
                        ├─ yes ─> tools ─> LLM
                        └─ no / blocked / already triggered ─> LLM
```

1. `src/harness/graph.py` — route a `cicd_tool` call to an approval node before
   `ToolNode` can execute it. The node checks the current report's deterministic
   outcome and whether CI/CD has already been triggered in this session. If the
   report is not passing or the trigger already ran, add a matching rejection
   `ToolMessage` and return to the LLM. Otherwise, call `interrupt()` with the
   proposed action. On approval, set the approval state and route to tool execution;
   on rejection, add a matching rejection `ToolMessage` and return to the LLM.
   Keep the CI/CD call isolated from other tool calls in the same AI message so
   approval applies only to the deployment request.
2. `src/harness/state.py` — retain the approval decision and add a per-thread
   `cicd_triggered: bool` initialized to `False`. Set it to `True` only after the
   CI/CD tool reports successful dispatch. Since the state is checkpointed, later
   turns in the same thread can block a second trigger.
3. `src/main.py` — handle the pause and reply. Detect
   `response["__interrupt__"]` and display its question. Treat the next yes/no
   message as `Command(resume=True/False)` using the same config and `thread_id`.
   Send only new messages during normal turns; the checkpointer retains history.
4. `src/harness/system/system_prompt.py` — this step is implemented. The prompt
   tells the model to answer report questions, offer deployment only when the
   current report passes, and call `cicd_tool` only when the user wants to proceed.
   The graph must enforce the passing-report and already-triggered checks.
5. `tests/harness/` — verify ordinary tools still loop through the LLM; CI/CD
   pauses before execution; approval executes once; rejection, failed/unknown
   reports, and repeated requests do not execute the tool and return to the LLM.

The current `cicd_tool` only prints and returns a simulation message. Later, replace
that behavior with the GitHub workflow dispatch. The `cicd_triggered` flag prevents
normal repeat requests after a successful dispatch is checkpointed. Handling a
process crash between a remote dispatch succeeding and the state update being
checkpointed would require an idempotency key or checking GitHub for the existing
run.
