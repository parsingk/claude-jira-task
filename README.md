# claude-jira-task

> 한국어 버전: [docs/ko/README.md](docs/ko/README.md)

A Claude Code plugin that bundles **Jira issue registration, status transitions, and per-task work isolation (separate worktree or current directory)** into a single workflow.

## Core features

| Feature | Behavior |
|---|---|
| `/jira-task <summary>` | Create a new Jira issue (walks through issue type, summary, description, assignee, Epic, labels, and isolation mode in order) |
| Repo-scoped default project | Asked only once on the first call inside a new repo, then stored in `.claude/jira-config.json` |
| Forced registration | For work that produces artifacts, skips the "register?" prompt and enters the registration flow directly |
| Automatic status transitions | Edit / Bash → `In Progress`, commit / PR → `Resolved` (only Closed requires a manual step) |
| Work isolation (chosen at registration) | Pick either **separate worktree** (sibling path `<repo>-<KEY>`, safe for running multiple tasks in parallel) or **current directory** (reuses dev server / IDE / browser context — recommended for frontend work). A new branch is created either way. |
| Active task tracking | Multi-task state stored in `.claude/active-jira-tasks.json` (an empty `worktree_path` means current-directory mode) |
| Version notice | On the first `/jira-task` call, compares the marketplace `origin/main` with the locally installed version and prints a one-line notice if a newer version exists (24h cache, best-effort, silent on failure) |

## Dependencies

| Item | Requirement | Notes |
|---|---|---|
| **Claude Code** | ≥ a version that supports the plugin system | All OSes |
| **Atlassian MCP server** | Anthropic's official Atlassian Remote MCP | See [Installing the Atlassian MCP](#installing-the-atlassian-mcp) below. If missing, an installation notice is printed automatically on the first `/jira-task` call. |
| **git** | ≥ 2.5 | Used for worktrees |
| **bash** | All OSes — built in on Linux/macOS, satisfied by Git Bash on Windows | The hook wrapper runs in bash |
| **Python** | 3.x (either `python3` or `python` on PATH is fine) | Runs the hook script. If missing, only the hook is disabled (the skill body keeps working). |

### Installing the Atlassian MCP

```
claude mcp add --transport http atlassian https://mcp.atlassian.com/v1/mcp
```

After installation, restart Claude Code — an OAuth screen appears. Authentication is required only once.

Official guide: https://support.atlassian.com/atlassian-rovo-mcp-server/docs/getting-started-with-the-atlassian-remote-mcp-server/

> If the MCP is missing when `/jira-task` is invoked after installing the plugin, the notice above is printed automatically and the registration flow stops — you can run the command above at that point.

## Installation

```
/plugin marketplace add <this-repo-url>
/plugin install <plugin-name>
```

After installation, restart Claude Code to activate the `/jira-task` slash command.

## First use

Inside a new repo folder:

```
/jira-task fix OAuth bug on the login screen
```

On the first call, the following flow runs automatically:

1. Pick a default project from the available Jira project list → saved to `.claude/jira-config.json`
2. Confirm issue type / summary / description / assignee / Epic / labels / **isolation mode** in order
3. Create the issue via `mcp__atlassian__createJiraIssue`
4. Branch by isolation mode — **separate worktree** creates a sibling worktree (`<repo>-<KEY>`) and moves the context into it; **current directory** just runs `git checkout -b <type>/<KEY>-<slug>` in the cwd
5. Auto-transitions to `In Progress` on the first file edit

Subsequent calls inside the same repo never ask for the default project again.

### Which isolation mode to pick

| Situation | Recommendation |
|---|---|
| Backend, agent, library work; possibly running multiple tasks in parallel | **Separate worktree** (default) |
| Frontend work — dev server hot reload, browser preview, and reusing the IDE index matter | **Current directory** |
| You only handle one task at a time | **Current directory** is lighter |
| Heavy reliance on local caches like `.env.local`, Docker volumes, or `node_modules` | **Current directory** (a worktree would force you to set them up again) |

## Recommended `.gitignore` for consuming repos

The two files this plugin creates hold **local, personal state** — don't commit them:

```gitignore
# Claude Code — local state for the claude-jira-task plugin
.claude/active-jira-tasks.json
.claude/jira-config.json
```

(Ignoring Claude Code's other personal setting `.claude/settings.local.json` is also recommended.)

## Subcommand summary

| Invocation | Meaning |
|---|---|
| `/jira-task <summary>` | New registration |
| `/jira-task list` | List currently active tasks |
| `/jira-task switch <KEY>` | Switch work context (moves into the worktree if any) |
| `/jira-task deactivate <KEY>` | Remove from the active list (Jira issue is left as-is) |
| `/jira-task config reset` | Drop this repo's default project — the next call will ask again |
| `/jira-task config set <KEY>` | Overwrite this repo's default project immediately |

For the full workflow rules see `skills/jira-task/SKILL.md`.

## Hook behavior — git commit gate

The plugin also registers a `PreToolUse` hook. Right before Claude runs `git commit` it checks:

1. Does the current repo have `.claude/jira-config.json`? (If not, the hook passes — workflow opt-out)
2. Does the current branch name contain an active task key (e.g. `TASK-123`)?

If neither matches, the hook blocks the commit and returns "register first with `/jira-task`" to Claude. Claude then enters the registration flow on the spot and retries the commit in the new worktree.

**Limitation**: The hook does not fire when `git commit` is run directly from a terminal or IDE outside Claude Code. To block that case as well, configure a `.git/hooks/pre-commit` in each repo.

## Modifying / extending

The workflow body lives in `skills/jira-task/SKILL.md`. To change the rules at the team level, edit that file and open a PR.
