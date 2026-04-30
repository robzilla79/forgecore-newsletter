# only changed parts
from utils import WORKSPACE, dump_json, load_text, issue_path_for_today, artifact_suffix_for_issue

# replace latest_issue_path usage in main

def main() -> int:
    contract_error = ""
    path = issue_path_for_today()
    try:
        path = ensure_issue_contract(path)
    except Exception as exc:
        contract_error = str(exc).strip() or "issue contract failed"
    text = load_text(path)

    # unchanged logic...

    result = {"passed": not errors, "checks": checks, "issue": path.as_posix()}

    suffix = artifact_suffix_for_issue(path)
    out_path = WORKSPACE / "state" / f"quality-gate-{suffix}.json"

    result["run_token"] = RUN_TOKEN
    result["artifact_path"] = out_path.as_posix()
    dump_json(out_path, result)
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1
