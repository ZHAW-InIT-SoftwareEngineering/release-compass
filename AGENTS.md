# Agent Guidelines

- Keep changes small, focused, and consistent with existing code.
- Use Python 3.14+ and keep dependencies minimal.
- Add or update tests when behavior changes.
- Run relevant checks before finishing and report their results.
- Preserve unrelated work in the working tree.
- If a new package is needed, pause work before changing dependencies or installing it. Tell the developer the exact `uv add <package>` command, listing only direct packages the task actually needs, not their transitive dependencies. The developer must run it manually in the terminal; resume only after the developer confirms the package was added and explicitly gives the go-ahead.
