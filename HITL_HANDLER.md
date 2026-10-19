# Human-in-the-loop interrupt handling

The approval flow has three responsibilities:

| Location | Responsibility |
|---|---|
| `src/harness/graph.py` | Requests approval with `interrupt(...)`; executes CI/CD only when the returned value `is True`. |
| `src/harness/interrupt_handler.py` | Parses human text: trims whitespace, normalizes capitalization, converts yes/no to booleans, and raises `ValueError` otherwise. |
| `src/main.py` → `run_chat()` | Displays requests, reads input, retries invalid answers, and resumes the graph. |

## Execution sequence

```text
Graph calls interrupt(payload)
→ LangGraph checkpoints and returns an Interrupt to the caller
→ run_chat reads Interrupt.value and displays the request
→ InterruptHandler parses the user's text
→ run_chat submits Command(resume={Interrupt.id: boolean})
→ LangGraph restarts the paused node
→ interrupt(...) returns that boolean
→ graph approves or rejects
```

The same `thread_id` loads the conversation checkpoint. `Interrupt.id` matches
each answer to its pending request. Our payload's `kind="cicd_approval"` selects
the parser; LangGraph does not interpret that field. See LangGraph's
[resume semantics](https://docs.langchain.com/oss/python/langgraph/interrupts#resuming-interrupts)
and [handling multiple interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts#handling-multiple-interrupts).

Because the node restarts on resume, code before `interrupt()` runs again.
Side effects there must be idempotent.

## Why the handler is called outside the graph

Interpreting terminal text belongs with the interaction. Invalid input can be
retried while execution stays paused. The graph retains the execution decision,
so parsing never triggers CI/CD itself. The outer interrupt loop handles
additional pauses after resuming.

| Human input | CLI behavior | Graph behavior |
|---|---|---|
| `yes`, including capitalization and surrounding whitespace | Resume with `True` | Set approval flag and route to tools |
| `no`, including capitalization and surrounding whitespace | Resume with `False` | Add a rejection tool message and route to the LLM |
| Anything else | Display the validation error and ask again | Remain paused |

The parser currently handles only CI/CD approval. Additional interrupt types
can have their own parser methods, selected through the payload's `kind` field.
Unknown kinds raise an error rather than being resumed with an assumed answer.

## How to derive this design

Trace the data and identify who owns each step:

1. **Who knows what requires approval?** The graph node creates the request.
2. **Who can talk to the human?** The CLI displays the request and collects input.
3. **What does the node need back?** A boolean; the parser converts text into that contract.
4. **What if conversion fails?** Ask again before resuming.
5. **How does the answer reach the right execution?** Resume with the interrupt ID and original thread.
6. **Can resuming produce another request?** Yes; repeat until no interrupts remain.

This gives each part one clear job. The checkpointer retains conversation history,
so the CLI sends the system prompt once and only new user messages on subsequent
turns.
