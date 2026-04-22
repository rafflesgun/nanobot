# Skills

nanobot supports two kinds of skills:

- built-in skills shipped with the repository under `nanobot/skills/`
- workspace skills stored under `workspace/skills/`

## Reading vs Writing

Two components now handle skills with different responsibilities:

- `SkillsLoader` reads and summarizes built-in and workspace skills for prompt construction.
- `SkillsManager` performs safe mutations of workspace skills only.

This split keeps the existing read path simple while giving the agent a constrained way to evolve reusable procedures.

## Workspace Skill Management

The `skill_manage` tool supports these workspace-only actions:

- `create`
- `replace`
- `patch`
- `delete`
- `apply_proposal`
- `reject_proposal`

Safety rules:

- only workspace skills under `workspace/skills/` can be modified
- bundled skills under `nanobot/skills/` are read-only
- skill names must be kebab-case
- frontmatter must contain matching `name` and non-empty `description`

## Dream Skill Proposals

Dream can identify repeatable workflows worth turning into a skill, but it no longer installs them directly.

Instead, Dream writes proposals under:

```text
workspace/
└── memory/
    └── skill-proposals/
        └── <name>.md
```

Proposal files use the same frontmatter/body format as a normal skill so they can be reviewed and promoted without translation.

## Review Flow

The learning loop is now review-first:

1. Dream detects a reusable workflow.
2. Dream writes `memory/skill-proposals/<name>.md`.
3. The agent or user reviews the proposal.
4. `skill_manage(action="apply_proposal", name="<name>")` installs it into `workspace/skills/<name>/SKILL.md`.
5. `skill_manage(action="reject_proposal", name="<name>")` deletes the proposal without installing it.

This keeps procedural learning explicit and reversible.
