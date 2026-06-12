---
name: troll_guard
track: bonus
kind: control
provider: none
requires_env: []
inputs: [text, mode]
outputs: [is_trollish, severity, signals, suggested_response]
side_effect: false
---
# troll_guard

Local heuristic detector for low-quality / troll / abusive prompts.
Returns a suggested safe redirection response and a small set of signals for debugging.

