"""MyCARE Docker監視 — 停止コンテナを検知して自動再起動する（Cronスクリプト）"""
import subprocess, json, sys

# 監視対象コンテナ
WATCHED_CONTAINERS = ["myknot_postgres"]

def get_container_status(name):
    r = subprocess.run(
        ["docker", "inspect", "--format", "{{.State.Status}}", name],
        capture_output=True, text=True
    )
    return r.stdout.strip() if r.returncode == 0 else None

def restart_container(name):
    r = subprocess.run(
        ["docker", "start", name],
        capture_output=True, text=True
    )
    return r.returncode == 0, r.stderr.strip() if r.returncode != 0 else ""

if __name__ == "__main__":
    restarted = []
    failed = []
    already_running = []

    for name in WATCHED_CONTAINERS:
        status = get_container_status(name)
        if status == "running":
            already_running.append(name)
        elif status is None:
            failed.append(f"{name}: container not found")
        else:
            ok, err = restart_container(name)
            if ok:
                restarted.append(name)
            else:
                failed.append(f"{name}: {err}")

    result = {
        "running": already_running,
        "restarted": restarted,
        "failed": failed,
        "action_taken": len(restarted) > 0 or len(failed) > 0
    }
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(1 if failed else 0)
