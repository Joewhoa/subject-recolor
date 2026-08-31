# Install the Subject Recolor Skill in DSH

The Python CLI performs the work. The Skill is the agent-facing operating playbook that makes a conversation follow the safe `doctor → plan → confirm → run → review` sequence.

## Recommended: copy into your own agent preset

Do not modify DSH's shipped preset installation. Copy this directory:

```text
skills/subject-recolor/
```

into the `skills/` directory of a user-authored preset, for example:

```text
%USERPROFILE%\.dsh\.agent-presets\<your-preset>\skills\subject-recolor\
```

The final file must be:

```text
<your-preset>/skills/subject-recolor/SKILL.md
```

Mount that user preset in DSH and start a new session. When the user asks for “按色卡批量换色” or similar work, the Skill description allows the agent to select this playbook.

The exact preset path can differ by DSH installation. Use the preset roster/path shown by your DSH environment; never edit the deployment's shipped preset directory.

## Zero-install use

In a session, explicitly reference the repository file and ask the agent to follow it:

```text
请读取 @skills/subject-recolor/SKILL.md，按这个流程处理 workspace 下最新的主体换色任务。
```

This does not provide automatic Skill discovery but uses the same workflow.

## Why no Cordis plugin is required

A DSH Skill supplies instructions; this repository already supplies the durable CLI, files, state machine and tests. A dynamic Cordis plugin is temporary to one running DSH process and is not necessary for GitHub portability. A future UI plugin may call the CLI, but it must not weaken the CLI's paid-call and uncertain-result guards.

## Agent request examples

```text
初始化一个 2026-09-02 的任务，主体是户外雨伞。
```

```text
检查最新任务，先告诉我原图、色卡、已完成数和新增付费调用数，不要直接生图。
```

```text
按刚才确认的范围执行；出现超时不要重试，完成后给我审阅页。
```
