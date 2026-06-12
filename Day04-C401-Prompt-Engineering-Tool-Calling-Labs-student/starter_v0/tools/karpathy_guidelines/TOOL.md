---
name: karpathy_guidelines
track: core
kind: local_knowledge
provider: None
requires_env: []
inputs: [query]
outputs: [guidelines]
side_effect: false
requires_confirmation: false
---

Karpathy-inspired coding guidelines extracted from https://github.com/multica-ai/andrej-karpathy-skills.
This tool returns a concise checklist and the four core principles (Think Before Coding, Simplicity First,
Surgical Changes, Goal-Driven Execution). Use it when you want the agent to follow conservative, test-driven,
and minimal-change coding behaviors or to produce a short checklist for code edits.
