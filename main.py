#!/usr/bin/env python3
"""
Print Slack messages from the last N minutes using slackcli.

Accepts either:
  - a conversation ID  (C... channel, G... private channel, D... DM)
  - a user ID          (U... / W...) -> resolves to your DM with that user

Usage:
  python slack_recent.py DXXXXXXXX 10
  python slack_recent.py UXXXXXXXX 30
  python slack_recent.py C0123456789 5 --workspace "My Team"
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime


def _run_slackcli(args, workspace=None):
    """Run a slackcli command with --json and return parsed JSON (or None if empty)."""
    cmd = ["slackcli", *args, "--json"]
    if workspace:
        cmd += ["--workspace", workspace]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except FileNotFoundError:
        sys.exit("slackcli not found on PATH. Install it first (brew install slackcli).")
    except subprocess.CalledProcessError as e:
        sys.exit(f"slackcli failed ({' '.join(cmd)}):\n{e.stderr.strip() or e.stdout.strip()}")

    out = result.stdout.strip()
    return json.loads(out) if out else None


def _as_list(data, *keys):
    """Pull a list out of slackcli JSON, whatever the top-level shape."""
    if data is None:
        return []
    if isinstance(data, list):
        return data
    for k in keys:
        if isinstance(data.get(k), list):
            return data[k]
    return []


def resolve_conversation_id(target_id, workspace=None):
    """If given a user ID, find the DM channel with that user; otherwise return as-is."""
    if not target_id.startswith(("U", "W")):
        return target_id

    data = _run_slackcli(["conversations", "list", "--types=im", "--limit=1000"], workspace)
    for convo in _as_list(data, "channels", "conversations"):
        if convo.get("user") == target_id:
            return convo["id"]

    sys.exit(f"No DM found with user {target_id}. Open a DM with them in Slack first.")


def get_recent_messages(target_id, minutes, workspace=None, limit=100):
    """
    Return messages from the last `minutes` minutes, oldest first.

    target_id: channel/DM ID (C/G/D...) or user ID (U/W...).
    """
    convo_id = resolve_conversation_id(target_id, workspace)
    data = _run_slackcli(["conversations", "read", convo_id, f"--limit={limit}"], workspace)

    since = time.time() - minutes * 60
    messages = [
        m for m in _as_list(data, "messages")
        if float(m.get("ts", 0)) > since
    ]
    return sorted(messages, key=lambda m: float(m["ts"]))


def print_recent_messages(target_id, minutes, workspace=None):
    """Print messages from the last `minutes` minutes. Prints nothing if there are none."""
    messages = get_recent_messages(target_id, minutes, workspace)
    for m in messages:
        when = datetime.fromtimestamp(float(m["ts"])).strftime("%Y-%m-%d %H:%M:%S")
        who = m.get("user_name") or m.get("username") or m.get("user") or "unknown"
        text = m.get("text", "").strip()
        print(f"[{when}] {who}: {text}")
    return messages


def main():
    parser = argparse.ArgumentParser(description="Print Slack messages from the last N minutes.")
    parser.add_argument("id", help="Channel/DM ID (C/G/D...) or user ID (U/W...)")
    parser.add_argument("minutes", type=int, nargs="?", default=10, help="Look-back window (default 10)")
    parser.add_argument("--workspace", help="slackcli workspace name or ID (optional)")
    args = parser.parse_args()

    found = print_recent_messages(args.id, args.minutes, args.workspace)
    sys.exit(0 if found else 1)  # exit 1 = nothing new, handy for scripts/cron


if __name__ == "__main__":
    main()