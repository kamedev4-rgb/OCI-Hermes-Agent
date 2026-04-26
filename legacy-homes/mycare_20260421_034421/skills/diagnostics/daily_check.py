"""MyCARE 定時診断スキル — MyKNOT の健全性を確認して Discord に報告する"""

import subprocess
import datetime

def run(ctx):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M JST")
    lines = [f"## MyCARE 定時診断レポート ({now})"]

    # 1. hermes-gateway サービス確認
    result = subprocess.run(
        ["systemctl", "--user", "is-active", "hermes-gateway"],
        capture_output=True, text=True
    )
    status = result.stdout.strip()
    lines.append(f"- hermes-gateway: {'✅ active' if status == 'active' else f'❌ {status}'}")

    # 2. PostgreSQL 確認
    result = subprocess.run(
        ["docker", "exec", "myknot_postgres", "pg_isready", "-U", "myknot"],
        capture_output=True, text=True
    )
    pg_ok = result.returncode == 0
    lines.append(f"- PostgreSQL: {'✅ accepting connections' if pg_ok else '❌ not ready'}")

    # 3. 直近1時間のメッセージ数確認
    result = subprocess.run(
        ["docker", "exec", "myknot_postgres", "psql", "-U", "myknot", "-d", "myknot",
         "-t", "-c",
         "SELECT COUNT(*) FROM mem0_memories WHERE created_at > NOW() - INTERVAL '1 hour';"],
        capture_output=True, text=True
    )
    count = result.stdout.strip() if result.returncode == 0 else "取得失敗"
    lines.append(f"- 直近1時間の Mem0 書き込み数: {count}")

    # 4. オープン中のインシデント確認
    result = subprocess.run(
        ["docker", "exec", "myknot_postgres", "psql", "-U", "myknot", "-d", "myknot",
         "-t", "-c",
         "SELECT COUNT(*) FROM incidents WHERE status = 'open';"],
        capture_output=True, text=True
    )
    open_incidents = result.stdout.strip() if result.returncode == 0 else "取得失敗"
    lines.append(f"- オープン中のインシデント: {open_incidents} 件")

    report = "\n".join(lines)
    ctx.send_message(channel="mycare", content=report)
    return report
