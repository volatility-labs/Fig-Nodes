from typing import Dict, List
import os
import importlib.util
import inspect
from nodes.base_node import BaseNode

def load_nodes(directories: List[str]) -> Dict[str, type]:
    registry = {}
    for dir_path in directories:
        abs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', dir_path))
        if not os.path.exists(abs_dir):
            continue
        for filename in os.listdir(abs_dir):
            if filename.endswith('.py') and filename != '__init__.py':
                module_path = os.path.join(abs_dir, filename)
                module_name = filename[:-3]
                spec = importlib.util.spec_from_file_location(module_name, module_path)
                module = importlib.util.module_from_spec(spec)
                module.__package__ = os.path.basename(dir_path)
                spec.loader.exec_module(module)
                for name, obj in vars(module).items():
                    if isinstance(obj, type) and issubclass(obj, BaseNode) and obj != BaseNode and not inspect.isabstract(obj):
                        registry[name] = obj
    return registry

NODE_REGISTRY = load_nodes(['nodes', 'plugins']) 