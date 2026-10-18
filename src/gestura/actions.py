import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

import requests

log = logging.getLogger("gestura.actions")


class Actions:
    def __init__(self, path: Path):
        self._rules: dict[str, dict] = json.loads(path.read_text("utf-8")) if path.exists() else {}
        self._pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="action")
        if self._rules:
            log.info("actions loaded from %s: %s", path, ", ".join(self._rules))

    def names(self) -> list[str]:
        return list(self._rules)

    def fire(self, event: dict, on_done: Callable[[str, str], None]) -> bool:
        rule = self._rules.get(event["name"])
        if not rule:
            return False
        self._pool.submit(self._send, rule, event, on_done)
        return True

    def _send(self, rule: dict, event: dict, on_done: Callable[[str, str], None]):
        headers = {k: os.path.expandvars(v) for k, v in (rule.get("headers") or {}).items()}
        body = rule["json"] if "json" in rule else event
        try:
            response = requests.request(
                rule.get("method", "POST"),
                os.path.expandvars(rule["url"]),
                json=body,
                headers=headers,
                timeout=rule.get("timeout", 3),
            )
            status = str(response.status_code)
        except requests.RequestException as e:
            status = f"error: {type(e).__name__}"
        log.info("action %s -> %s", event["name"], status)
        on_done(event["name"], status)
