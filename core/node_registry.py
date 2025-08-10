from typing import Dict, List
import os
import importlib.util
import inspect
from nodes.base.base_node import BaseNode

def load_nodes(directories: List[str]) -> Dict[str, type]:
    registry = {}
    for dir_path in directories:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', dir_path))
        for root, _, files in os.walk(base_dir):
            for filename in files:
                if filename.endswith('.py') and filename != '__init__.py':
                    module_path = os.path.join(root, filename)
                    module_name = f"{dir_path}.{os.path.splitext(filename)[0]}"
                    spec = importlib.util.spec_from_file_location(module_name, module_path)
                    module = importlib.util.module_from_spec(spec)
                    # Adjust package to allow for relative imports within the nodes directory
                    package_name = dir_path.split('/')[0]
                    module.__package__ = package_name
                    spec.loader.exec_module(module)
                    for name, obj in vars(module).items():
                        if isinstance(obj, type) and issubclass(obj, BaseNode) and obj != BaseNode and not inspect.isabstract(obj):
                            registry[name] = obj
    return registry

NODE_REGISTRY = load_nodes(['nodes/impl', 'plugins']) 