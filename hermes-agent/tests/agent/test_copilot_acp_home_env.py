import importlib


def test_acp_subprocess_env_uses_claude_code_home(monkeypatch):
    monkeypatch.setenv("HOME", "/home/ubuntu/.hermes/profiles/myknot/home")
    monkeypatch.setenv("CLAUDE_CODE_HOME", "/home/ubuntu")

    from agent import copilot_acp_client

    module = importlib.reload(copilot_acp_client)

    env = module._acp_subprocess_env()

    assert env["HOME"] == "/home/ubuntu"
    assert "profiles/myknot" not in env["HOME"]


def test_run_prompt_passes_real_home_to_acp_subprocess(monkeypatch):
    monkeypatch.setenv("HOME", "/home/ubuntu/.hermes/profiles/myknot/home")
    monkeypatch.setenv("CLAUDE_CODE_HOME", "/home/ubuntu")

    from agent import copilot_acp_client

    module = importlib.reload(copilot_acp_client)
    captured = {}

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        captured.update(kwargs)
        raise FileNotFoundError("stop after capturing Popen kwargs")

    monkeypatch.setattr(module.subprocess, "Popen", fake_popen)

    client = module.CopilotACPClient(command="claude", args=["--print"])
    try:
        client._run_prompt("test", timeout_seconds=1)
    except RuntimeError as exc:
        assert "Could not start Copilot ACP command" in str(exc)

    assert captured["cmd"] == ["claude", "--print"]
    assert captured["env"]["HOME"] == "/home/ubuntu"
    assert "profiles/myknot" not in captured["env"]["HOME"]
