# 4. Procedures are versioned data with a static write-before-verify check

Status: accepted

Multi-step actions (refund, cancel, change email) are YAML step graphs with a small expression
language rather than prompts or code. A release pins a version of each. Before anything runs, a
depth-first walk over every path flags any write step reachable without a verification step.

Consequences: the riskiest class of bug (acting on an account for someone who is not its owner) is
caught in seconds without traffic. Policy errors that are structurally fine (a 30-day window where
policy says 14) are not; the safety suite catches those with simulated customers.
