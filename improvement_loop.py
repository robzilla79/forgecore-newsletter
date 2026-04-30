# key change: use issue_path_for_today instead of scanning list
from utils import issue_path_for_today

# replace main logic

def main() -> int:
    path = issue_path_for_today()
    if not path.exists():
        emit_result(changed=False, issue_path=None, reason="no issue for slot")
        return 0

    changed, reason = improve_issue(path)
    emit_result(
        changed=changed,
        issue_path=path.as_posix() if changed else None,
        reason=reason,
    )
    return 0
