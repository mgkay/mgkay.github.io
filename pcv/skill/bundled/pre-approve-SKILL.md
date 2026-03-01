# /pre-approve — Permission Pre-Flight

Scan a plan file to identify all Bash/tool permissions that will be needed during
execution, compare against current settings, and get gaps approved upfront — enabling
uninterrupted execution.

## Invocation

```
/pre-approve [plan-file]        # with path argument
/pre-approve                    # prompts for plan file path
```

## Workflow

### Step 1: Load the Plan

- If `$ARGUMENTS` contains a file path, read that file.
- If `$ARGUMENTS` is empty, use AskUserQuestion to prompt for the plan file path.
- Confirm the file was loaded successfully.

### Step 2: Load Current Permissions

Read both settings files (skip gracefully if either is missing):
- `~/.claude/settings.json` (global)
- `.claude/settings.json` (project-level, relative to working directory)

Parse the `permissions.allow` arrays from both. Merge into a single "currently allowed"
list. Also note any `permissions.deny` entries.

### Step 3: Scan Plan for Required Actions

Analyze the plan text for permission-requiring actions:

- **Explicit CLI commands**: Look for code blocks and inline code containing shell
  commands (e.g., `quarto render`, `magick convert`, `tlmgr install`, `pip install`).
- **Action verbs mapped to tools**: Interpret action descriptions (e.g., "convert WMF
  files" → `magick`, "render slides" → `quarto`, "install packages" → `pip`/`npm`/etc.).
- **Script executions**: Python/Julia/Node scripts referenced by name.
- **Tool references**: Agent, WebFetch, WebSearch, NotebookEdit, etc.
- **File operation patterns**: Directories to be created (`mkdir`), bulk file operations.

Produce a **deduplicated** list of permission patterns in Claude Code format:
- Bash permissions: `Bash(command *)` format
- Tool permissions: `ToolName` or `ToolName(*)` format

### Step 4: Identify Gaps

Compare each required pattern against the merged allow list:
- A pattern is **covered** if it matches an existing allow entry (exact match or
  the existing entry is a superset via wildcard).
- A pattern is a **gap** if no existing entry covers it.
- A pattern is **denied** if it matches a deny entry (flag for user attention).

### Step 5: Present Manifest

Display the results as a clear table:

```
Permission Audit for: [plan file name]

Already covered:
  Bash(quarto *)     global settings
  Bash(python *)     global settings
  Bash(git *)        global settings

Gaps found:
  Bash(magick *)     ImageMagick conversion (WMF→PNG)
  Bash(tlmgr *)      LaTeX package installation

Denied (requires review):
  [any matches against deny list]
```

If there are no gaps, report "All permissions covered" and stop.

If there are gaps, use AskUserQuestion to ask the user how to handle each gap.
Present options for each gap (or batch similar ones):
- **(a) Add to project settings** (`.claude/settings.json`) **(Recommended)**
- **(b) Add to global settings** (`~/.claude/settings.json`)
- **(c) Skip** (will prompt at runtime as usual)

### Step 6: Apply Approved Permissions

For each approved permission:
1. Read the target settings file.
2. Add the new pattern to `permissions.allow` (maintain sorted order if possible).
3. Write the updated file.
4. Confirm completion with a summary of changes made.

Do NOT modify deny lists. Do NOT remove existing permissions.

## Rules

- Never add to the deny list — only the allow list.
- Preserve existing settings file structure (other keys like `hooks`, `model`, etc.).
- If a settings file doesn't exist yet, create it with a minimal valid structure:
  `{"permissions": {"allow": [...]}}`.
- Use Read/Edit tools for file modifications, not Bash.
- This is an idempotent skill — running it twice on the same plan should report
  all permissions as "already covered" on the second run.
