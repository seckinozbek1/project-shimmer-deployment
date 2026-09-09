"""Measurement harness for single agent calls.

Not a pipeline phase and not imported by one. The harness exists to ask narrow
questions of a single agent on a single unit of material against a single rule,
on either backend, so that a claim about the review path can be checked against
a number instead of an impression.

Three parts:
  run_agent        one agent, one unit, one rule, one backend, real prompt
  probe_arithmetic the model's arithmetic with no review framing at all
  score_envelope   compliance, verdict accuracy and latency over a batch

The harness carries no domain knowledge. Units, rules and reference passages are
read from files the operator points it at.
"""
