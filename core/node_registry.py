# core/node_registry.py
# This module handles dynamic loading of node classes from specified directories.
# It allows for easy extension by placing new node implementations in 'nodes/impl' or 'plugins'.

from typing import Dict, List
import os
import importlib.util
import inspect
from nodes.base.base_node import BaseNode

def load_nodes(directories: List[str]) -> Dict[str, type]:
    """
    Loads all concrete subclasses of BaseNode from the given directories.
    
    Args:
        directories: List of relative paths to search for node modules.
    
    Returns:
        Dictionary mapping node class names to their types.
    
    Note: Skips abstract classes and __init__.py files.
    """
    registry = {}
    for dir_path in directories:
        # Support absolute and relative directories
        if os.path.isabs(dir_path):
            base_dir = dir_path
        else:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', dir_path))
        for root, _, files in os.walk(base_dir):
            for filename in files:
                if filename.endswith('.py') and filename != '__init__.py':
                    module_path = os.path.join(root, filename)
                    # Build a module name reflecting relative path from base_dir
                    rel_path = os.path.relpath(module_path, start=os.path.dirname(os.path.dirname(__file__)))
                    module_name = rel_path.replace(os.sep, '.').rsplit('.py', 1)[0]
                    spec = importlib.util.spec_from_file_location(module_name, module_path)
                    module = importlib.util.module_from_spec(spec)
                    # Adjust package to allow for relative imports within the nodes directory
                    package_name = module_name.split('.')[0]
                    module.__package__ = package_name
                    spec.loader.exec_module(module)
                    for name, obj in vars(module).items():
                        if isinstance(obj, type) and issubclass(obj, BaseNode) and obj != BaseNode and not inspect.isabstract(obj):
                            registry[name] = obj
    return registry

extra_dirs_env = os.getenv('FIG_NODES_PATHS', '')
extra_dirs: List[str] = [p for p in extra_dirs_env.split(':') if p]

NODE_REGISTRY = load_nodes(['nodes/core', 'nodes/plugins', *extra_dirs])

# Developer Notes:
# To add a new node:
# 1. Create a new .py file in nodes/core/ or nodes/plugins/.
# 2. Define a class inheriting from BaseNode (or StreamingNode/UniverseNode).
# 3. Implement required attributes (inputs, outputs, etc.) and execute() method.
# 4. The node will be automatically registered and available in the system.
# 5. For UI parameters, define params_meta list on the class. 