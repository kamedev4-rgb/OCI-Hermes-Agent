#!/usr/bin/env python3
"""
Discord にローカルファイルを添付送信するユーティリティ。
slides スキルから呼び出す。

Usage:
  python3 discord_send_file.py <file_path> [message] [channel_id]

  channel_id を省略すると .env の DISCORD_DEFAULT_CHANNEL または
  DISCORD_CHANNEL_ID を使う。
"""
import os
import sys
import pathlib
import urllib.request
import urllib.parse

def _load_env(env_path: str) -> dict:
    env = {}
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, _, v = line.partition('=')
                env[k.strip()] = v.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return env

def send_file(file_path: str, message: str = "", channel_id: str = "") -> None:
    hermes_home = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))
    env = _load_env(os.path.join(hermes_home, ".env"))

    token = env.get("DISCORD_BOT_TOKEN") or os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        print("ERROR: DISCORD_BOT_TOKEN not found in .env", file=sys.stderr)
        sys.exit(1)

    if not channel_id:
        channel_id = (
            env.get("DISCORD_DEFAULT_CHANNEL")
            or env.get("DISCORD_CHANNEL_ID")
            or os.environ.get("DISCORD_CHANNEL_ID", "")
        )
    if not channel_id:
        # profiles/myknot/config.yaml の allowed_channels 先頭を使う
        config_path = os.path.join(hermes_home, "profiles", "myknot", "config.yaml")
        try:
            with open(config_path) as f:
                for line in f:
                    if "allowed_channels" in line and "'" in line:
                        # 例: allowed_channels: '1492863629173719050'
                        parts = line.split("'")
                        if len(parts) >= 2 and parts[1].strip().isdigit():
                            channel_id = parts[1].strip()
                            break
        except FileNotFoundError:
            pass

    if not channel_id:
        print("ERROR: Discord channel_id not found", file=sys.stderr)
        sys.exit(1)

    file_path = str(pathlib.Path(file_path).expanduser().resolve())
    if not os.path.isfile(file_path):
        print(f"ERROR: file not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    filename = os.path.basename(file_path)
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"

    # multipart/form-data で送信
    boundary = "----HermesBoundary7f3d9a"
    body_parts = []

    if message:
        body_parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="content"\r\n\r\n'
            f"{message}\r\n"
        )

    with open(file_path, "rb") as fh:
        file_data = fh.read()

    ext = pathlib.Path(filename).suffix.lower()
    mime_map = {
        ".pdf": "application/pdf",
        ".html": "text/html",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
    }
    mime = mime_map.get(ext, "application/octet-stream")

    header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="files[0]"; filename="{filename}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode()
    footer = f"\r\n--{boundary}--\r\n".encode()

    body = b"".join(
        [p.encode() for p in body_parts]
    ) + header + file_data + footer

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bot {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            status = resp.status
            print(f"OK: Discord file sent (status={status}, channel={channel_id}, file={filename})")
    except urllib.error.HTTPError as e:
        body_err = e.read().decode(errors="replace")
        print(f"ERROR: HTTP {e.code} - {body_err}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("Usage: discord_send_file.py <file_path> [message] [channel_id]")
        sys.exit(1)
    send_file(
        file_path=args[0],
        message=args[1] if len(args) > 1 else "",
        channel_id=args[2] if len(args) > 2 else "",
    )
