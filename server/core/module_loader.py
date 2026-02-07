from __future__ import annotations

import importlib.util
import json
import os
import sys
from dataclasses import dataclass
from typing import Any

from .types import ModuleConfig


@dataclass
class LoadedModule:
    config: ModuleConfig
    module: Any


def _load_python_module(module_path: str, module_id: str) -> Any:
    spec = importlib.util.spec_from_file_location(
        f"modules.{module_id}", os.path.join(module_path, "module.py")
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module.py for {module_id}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_modules(modules_root: str) -> list[LoadedModule]:
    loaded: list[LoadedModule] = []
    if not os.path.isdir(modules_root):
        return loaded

    for entry in os.listdir(modules_root):
        module_path = os.path.join(modules_root, entry)
        if not os.path.isdir(module_path):
            continue

        config_path = os.path.join(module_path, "module.json")
        if not os.path.isfile(config_path):
            continue

        with open(config_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        config = ModuleConfig.model_validate(raw)

        module = _load_python_module(module_path, config.id)
        loaded.append(LoadedModule(config=config, module=module))

    return loaded


def build_registry(modules_root: str) -> dict[str, LoadedModule]:
    registry: dict[str, LoadedModule] = {}
    for loaded in load_modules(modules_root):
        registry[loaded.config.id] = loaded
    return registry
