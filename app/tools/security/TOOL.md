---
name: security_scan
track: bonus
kind: control
provider: none
requires_env: []
inputs: [text, redact, max_findings]
outputs: [contains_secrets, findings, redacted_text]
side_effect: false
---
# security_scan

Local tool to detect and redact likely secrets (API keys / tokens) from text before sharing.
Use for sanitizing logs, transcripts, and pasted configuration snippets.

