"""Built-in boot-md hook -- run ~/.hermes/BOOT.md on gateway startup.

This hook is always registered. It silently skips if no BOOT.md exists.
To activate, create ``~/.hermes/BOOT.md`` with instructions for the
agent to execute on every gateway restart.

Example BOOT.md::

    # Startup Checklist

    1. Check if any cron jobs failed overnight
    2. Send a status update to Discord #general
    3. If there are errors in /opt/app/deploy.log, summarize them

The agent runs in a background thread so it does not block gateway
startup. If nothing needs attention, it replies with [SILENT] to
suppress delivery.
"""

import logging
import threading

logger = logging.getLogger("hooks.boot-md")

from hermes_constants import get_default_hermes_root
HERMES_ROOT = get_default_hermes_root()
BOOT_FILE = HERMES_ROOT / "BOOT.md"


def _build_boot_prompt(content: str) -> str:
    """Wrap BOOT.md content in a system-level instruction."""
    return (
        "You are running a startup boot checklist. Follow the BOOT.md "
        "instructions below exactly.\n\n"
        "---\n"
        f"{content}\n"
        "---\n\n"
        "Execute each instruction. If you need to send a message to a "
        "platform, use the send_message tool.\n"
        "If nothing needs attention and there is nothing to report, "
        "reply with ONLY: [SILENT]"
    )


def _run_boot_agent(content: str) -> None:
    """Spawn a one-shot agent session to execute the boot instructions."""
    try:
        from run_agent import AIAgent
        from hermes_cli.config import load_config

        _cfg = load_config()
        _model_cfg = _cfg.get("model", {})
        _model = _model_cfg.get("default") or ""
        _provider = _model_cfg.get("provider") or ""
        _base_url = _model_cfg.get("base_url") or ""

        prompt = _build_boot_prompt(content)
        agent = AIAgent(
            model=_model,
            provider=_provider,
            base_url=_base_url,
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
            max_iterations=20,
        )
        result = agent.run_conversation(prompt)
        if result.get("failed") or not result.get("completed"):
            logger.error(
                "boot-md agent did not complete (failed=%s, completed=%s): %s",
                result.get("failed"),
                result.get("completed"),
                (result.get("error") or "")[:200],
            )
            return
        response = result.get("final_response") or ""
        if response and "[SILENT]" not in response:
            logger.info("boot-md completed: %s", response[:200])
        else:
            logger.info("boot-md completed (nothing to report)")
    except Exception as e:
        logger.error("boot-md agent failed: %s", e)


async def handle(event_type: str, context: dict) -> None:
    """Gateway startup handler -- run BOOT.md if it exists."""
    if not BOOT_FILE.exists():
        return

    content = BOOT_FILE.read_text(encoding="utf-8").strip()
    if not content:
        return

    logger.info("Running BOOT.md (%d chars)", len(content))

    # Run in a background thread so we do not block gateway startup.
    thread = threading.Thread(
        target=_run_boot_agent,
        args=(content,),
        name="boot-md",
        daemon=True,
    )
    thread.start()
