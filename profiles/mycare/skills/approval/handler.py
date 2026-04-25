"""MyCARE 承認フロースキル — !approve / !reject コマンドを処理する"""

import subprocess
import uuid

def issue_token(ctx, incident_id: int, action: str, params: dict = None):
    """承認トークンを発行して Discord に通知する"""
    result = subprocess.run(
        ["docker", "exec", "myknot_postgres", "psql", "-U", "myknot", "-d", "myknot",
         "-t", "-c",
         f"INSERT INTO approval_tokens (incident_id, action, params) "
         f"VALUES ({incident_id}, '{action}', '{{}}'::jsonb) RETURNING token;"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return None
    token = result.stdout.strip()
    return token


def handle_approve(ctx, token: str):
    """!approve {token} を受け取って修復を実行する"""
    # トークンの有効性確認
    result = subprocess.run(
        ["docker", "exec", "myknot_postgres", "psql", "-U", "myknot", "-d", "myknot",
         "-t", "-c",
         f"SELECT action, status, expires_at > NOW() AS valid "
         f"FROM approval_tokens WHERE token = '{token}';"],
        capture_output=True, text=True
    )
    if result.returncode != 0 or not result.stdout.strip():
        ctx.send_message(channel="mycare", content="❌ トークンが見つかりません。")
        return

    row = result.stdout.strip().split("|")
    if len(row) < 3:
        ctx.send_message(channel="mycare", content="❌ トークンの読み取りに失敗しました。")
        return

    action = row[0].strip()
    status = row[1].strip()
    valid = row[2].strip() == "t"

    if status != "pending":
        ctx.send_message(channel="mycare", content=f"❌ このトークンは既に {status} です。")
        return
    if not valid:
        ctx.send_message(channel="mycare", content="❌ トークンの有効期限が切れています。")
        return

    # 修復実行
    ctx.send_message(channel="mycare", content=f"🔧 承認されました。修復を実行します: `{action}`")
    _execute_repair(ctx, action, token)


def handle_reject(ctx, token: str):
    """!reject {token} を受け取ってキャンセルする"""
    subprocess.run(
        ["docker", "exec", "myknot_postgres", "psql", "-U", "myknot", "-d", "myknot",
         "-c",
         f"UPDATE approval_tokens SET status = 'rejected' WHERE token = '{token}';"],
        capture_output=True, text=True
    )
    ctx.send_message(channel="mycare", content="✅ 修復をキャンセルしました。")


def _execute_repair(ctx, action: str, token: str):
    """修復テンプレートを実行する"""
    ALLOWED_ACTIONS = {
        "restart_hermes_gateway": lambda: subprocess.run(
            ["systemctl", "--user", "restart", "hermes-gateway"],
            capture_output=True, text=True
        ),
        "restart_postgres": lambda: subprocess.run(
            ["docker", "restart", "myknot_postgres"],
            capture_output=True, text=True
        ),
    }

    if action not in ALLOWED_ACTIONS:
        ctx.send_message(channel="mycare", content=f"❌ 未知のアクション: `{action}`")
        return

    result = ALLOWED_ACTIONS[action]()
    success = result.returncode == 0

    # トークンを完了に更新
    subprocess.run(
        ["docker", "exec", "myknot_postgres", "psql", "-U", "myknot", "-d", "myknot",
         "-c",
         f"UPDATE approval_tokens SET status = 'approved' WHERE token = '{token}';"],
        capture_output=True
    )

    if success:
        ctx.send_message(channel="mycare", content=f"✅ 修復完了: `{action}`")
    else:
        ctx.send_message(channel="mycare",
                         content=f"❌ 修復失敗: `{action}`\n```{result.stderr}```")
