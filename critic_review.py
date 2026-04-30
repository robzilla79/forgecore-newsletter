# truncated for brevity: same file but replace latest_issue_path() usage

from utils import WORKSPACE, dump_json, load_project_env, load_text, issue_path_for_today, artifact_suffix_for_issue

# ... unchanged above ...

def main() -> int:
    path = issue_path_for_today()
    suffix = artifact_suffix_for_issue(path)
    out_path = WORKSPACE / "state" / f"critic-review-{suffix}.json"

    try:
        result = evaluate_issue(path)
    except Exception as exc:
        result = {
            "passed": False,
            "issue": path.as_posix(),
            "overall_score": 0.0,
            "weak_categories": ["critic_runtime_failure"],
            "must_fix": ["Resolve critic runtime/model failure before publish."],
            "rewrite_plan": ["Fix critic."],
            "summary": f"critic_review failed: {exc}",
            "verdict": "reject",
        }

    result["run_token"] = RUN_TOKEN
    result["artifact_path"] = out_path.as_posix()
    dump_json(out_path, result)
    print(json.dumps(result, indent=2))
    return 0 if result.get("passed") else 1
