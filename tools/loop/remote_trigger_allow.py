"""PreToolUse hook: allow exactly one RemoteTrigger call, the emergency wake (Seckin 18 November 2026 23:51 and
19 November 2026 14:58).

Reads the hook's JSON on standard input. When tool_name is "RemoteTrigger", tool_input.action is "run" and
tool_input.trigger_id is the wake trigger, it prints the allow decision. In every other case it prints nothing
and exits 0, so Claude Code's normal permission rules decide. It never fails a call: any error also prints
nothing and exits 0.
"""
import json
import sys

WAKE_TRIGGER = "trig_01CRyVDA63iUXtMAeYweiJGq"
ALLOW = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
                                "permissionDecisionReason": "Seçkin onayı 18 Kasım 23:51 ve 19 Kasım 14:58"}}


def decide(event):
    if not isinstance(event, dict) or event.get("tool_name") != "RemoteTrigger":
        return None
    tool_input = event.get("tool_input") or {}
    if tool_input.get("action") == "run" and tool_input.get("trigger_id") == WAKE_TRIGGER:
        return ALLOW
    return None


def main():
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        out = decide(json.loads(raw)) if raw.strip() else None
    except Exception:
        out = None
    if out is not None:
        sys.stdout.buffer.write(json.dumps(out, ensure_ascii=False).encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
