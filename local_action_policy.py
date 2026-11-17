"""Central allowlist for local desktop assistant actions.

Unknown actions are denied by default. Confirmation does not persist as a grant.
"""
READ_ONLY = frozenset({"search_files", "recent_files", "preview_file", "list_tasks", "view_plan", "view_focus"})
CONFIRM = frozenset({"save_note", "save_memory", "analyze_file", "create_task", "complete_task", "update_task", "snooze_reminder", "save_plan", "save_focus"})
DENIED = frozenset({"delete_file", "rename_file", "run_program", "shell_command"})


def permission_for(action):
    if action in READ_ONLY:
        return "automatic"
    if action in CONFIRM:
        return "confirm"
    return "denied"


def may_execute(action, confirmed=False):
    permission = permission_for(action)
    return permission == "automatic" or (permission == "confirm" and confirmed)
