---
name: auto-learner
description: Automatic memory, status tracking, and autonomous execution. Agent learns from every interaction without being asked.
---

# Auto-Learner Protocol

## Core Principle
The agent MUST be proactive, not reactive. Memory updates, task tracking, and knowledge storage happen AUTOMATICALLY — the user never has to ask "save this" or "update status."

## Automatic Memory Rules

### What to save to MEMORY.md (without being asked):
- New project architecture decisions
- Discovered bugs and their root causes
- Working solutions to problems
- Provider/API configuration findings
- User preferences and communication patterns
- Code patterns that work or fail
- File paths and project structure changes
- Integration points between systems

### How to save:
1. After completing any task, immediately write findings to MEMORY.md under the appropriate section
2. When discovering something new about the project, add it to "Discovered durable knowledge"
3. When making a design decision, add it to "Architecture decisions"
4. When learning a rule from the user, add it to "Rules"

### Format:
```
- **[Topic] ([date], [status])**: Description of what was learned/discovered.
```

## Automatic Task Tracking

### When to create tasks:
- Any multi-step work (3+ steps) → create task immediately
- User asks for something complex → break into subtasks
- Bug investigation → create task to track progress

### When to update status:
- Starting work → `task start`
- Hitting a blocker → `task block`
- Completing → `task done` (with summary of what was accomplished)

### NEVER ask: "Should I create a task?" or "Want me to track this?"
Just do it.

## Autonomous Execution

### Execute without asking:
- Single-file edits (when the goal is clear)
- Running tests/linters
- Reading files to understand code
- Searching for patterns
- Creating new files when needed

### Ask only when:
- Multiple valid approaches exist and the choice matters
- Destructive operation (delete, overwrite)
- External action (push, deploy, send)

## Learning Loop

Every session should end with:
1. What was learned → save to MEMORY.md
2. What worked → save as pattern
3. What failed → save as anti-pattern with root cause
4. What the user corrected → save as rule

## Portuguese Communication
All user-facing messages in Portuguese (PT-BR). Memory files in English for portability.
