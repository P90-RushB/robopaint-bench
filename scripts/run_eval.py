"""Launch AgentArk's existing evaluator with sandbox-safe config selection.

This command starts Unity/model evaluation. prepare_run.py does not call it.
"""
import argparse
from pathlib import Path
import os

import yaml

TASK_PATH_OVERRIDES = (
    "AGENTARK_MOD_PATH", "AGENT_ARK_MOD_PATH", "AGENTARK_TASK107_CONFIG",
    "AGENTARK_TASK107_REFERENCE_DIRECTORY",
)


def main(args=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    args = parser.parse_args(args)
    path = Path(args.config).expanduser().resolve(strict=True)
    cfg = yaml.safe_load(path.read_text("utf-8"))
    if (not isinstance(cfg, dict) or not Path(cfg.get("env_cfg", {}).get("env_path", "")).is_absolute()
            or not cfg.get("env_cfg", {}).get("runtime_sandbox", {}).get("enabled")):
        parser.error("Use the isolated eval.yaml produced by scripts/prepare_run.py.")
    # Task107 prioritizes these variables above the Player's own Mods path.
    # Empty entries also prevent .env loading from restoring template/Editor
    # paths. Shell variables outside this process are unchanged.
    for name in TASK_PATH_OVERRIDES:
        os.environ[name] = ""
    from agent_ark.ark_eval.run_api_agent import main as agentark_main
    args.config = str(path)
    return agentark_main(args)


if __name__ == "__main__":
    main()
