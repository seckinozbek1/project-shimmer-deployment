"""PreToolUse hook: allow the lead's writes to Seckin's control panel only (Seckin 19 November 2026 18:17 and 18:19,
"Açık izin veriyorum. Açık onay."; SUPERVISOR_INBOX G-20261119-1820).

Reads the hook's JSON on standard input. It prints the allow decision only when tool_name is "ArtifactData", the
url names the panel artifact (slug PANEL_SLUG, exactly as a path segment), and the call is a read or a single write
to an allowed path: collection "panel" with doc_id "durum", or a collection that is "mesajlar" or starts with
"mesajlar/". A batch is allowed only when every entry is a write to an allowed path. In every other case it prints
nothing and exits 0, so Claude Code's normal permission rules decide (in the loop's dontAsk mode: refused). It never
fails a call: any error also prints nothing and exits 0.
"""
import json
import sys

PANEL_SLUG = "3580e2cf-7ca1-444b-a7a6-eca119952e23"
READS = ("get", "list", "query")
WRITES = ("set", "update", "str_replace", "delete")
ALLOW = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
                                "permissionDecisionReason": "Seçkin onayı 19 Kasım 18:19 (yalnız panel/durum ve mesajlar/)"}}


def _panel_url(url):
    if not isinstance(url, str):
        return False
    path = url.split("?", 1)[0].split("#", 1)[0].rstrip("/")
    return (path.startswith("https://claude.ai/code/artifact/") or path.startswith("https://claude.ai/artifact/")) \
        and path.rsplit("/", 1)[-1] == PANEL_SLUG


def _allowed_path(collection, doc_id):
    if not isinstance(collection, str):
        return False
    if collection == "panel":
        return doc_id == "durum"
    return collection == "mesajlar" or collection.startswith("mesajlar/")


def decide(event):
    if not isinstance(event, dict) or event.get("tool_name") != "ArtifactData":
        return None
    ti = event.get("tool_input") or {}
    if not _panel_url(ti.get("url")) or ti.get("as_level"):
        return None
    action = ti.get("action")
    if action in READS or action in WRITES:
        return ALLOW if _allowed_path(ti.get("collection"), ti.get("doc_id")) else None
    if action == "batch":
        writes = ti.get("writes")
        if isinstance(writes, list) and writes and all(
                isinstance(w, dict) and w.get("op") in ("set", "update", "delete")
                and _allowed_path(w.get("collection"), w.get("doc_id")) for w in writes):
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
