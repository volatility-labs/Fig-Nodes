# core/node_registry.py
# This module handles dynamic loading of node classes from specified directories.

from typing import List, Optional
import os
import importlib.util
import inspect
import logging
from core.types_registry import NodeRegistry
from nodes.base.base_node import Base

logger = logging.getLogger(__name__)

def load_nodes(directories: List[str]) -> NodeRegistry:
    """
    Loads all concrete subclasses of Base from the given directories.
    
    Args:
        directories: List of relative paths to search for node modules.
    
    Returns:
        Dictionary mapping node class names to their types.
    
    Note: Skips abstract classes and __init__.py files.
    To support extensibility, explicitly imports __init__.py in each subdirectory first
    to run any initialization code (e.g., type registrations via register_type).
    """
    registry: NodeRegistry = {}
    for dir_path in directories:
        base_dir: Optional[str] = None
        if os.path.isabs(dir_path):
            base_dir = dir_path
        else:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', dir_path))
        for root, _subdirs, files in os.walk(base_dir):
            # Explicitly import __init__.py if it exists to run extension registrations
            init_path = os.path.join(root, '__init__.py')
            if os.path.exists(init_path):
                # Build module name for __init__.py
                rel_path = os.path.relpath(root, start=os.path.dirname(os.path.dirname(__file__)))
                module_name = rel_path.replace(os.sep, '.')
                if module_name.endswith('.'):  # Handle root package
                    module_name = module_name[:-1]
                spec = importlib.util.spec_from_file_location(module_name, init_path)
                if spec is None or spec.loader is None:
                    logger.warning(f"Failed to get spec for {init_path}")
                    continue
                module = importlib.util.module_from_spec(spec)
                module.__package__ = module_name.rsplit('.', 1)[0] if '.' in module_name else module_name
                try:
                    spec.loader.exec_module(module)
                except Exception as e:
                    logger.warning(f"Failed to import __init__.py in {root}: {e}")
            for filename in files:
                if filename.endswith('.py') and filename != '__init__.py':
                    module_path = os.path.join(root, filename)
                    # Build a module name reflecting relative path from base_dir
                    rel_path = os.path.relpath(module_path, start=os.path.dirname(os.path.dirname(__file__)))
                    module_name = rel_path.replace(os.sep, '.').rsplit('.py', 1)[0]
                    spec = importlib.util.spec_from_file_location(module_name, module_path)
                    if spec is None or spec.loader is None:
                        logger.warning(f"Failed to get spec for {module_path}")
                        continue
                    module = importlib.util.module_from_spec(spec)
                    # Adjust package to allow for relative imports within the nodes directory
                    package_name = module_name.split('.')[0]
                    module.__package__ = package_name
                    spec.loader.exec_module(module)
                    for name, obj in vars(module).items():
                        if isinstance(obj, type) and issubclass(obj, Base) and obj != Base and not inspect.isabstract(obj):
                            registry[name] = obj
    return registry

NODE_REGISTRY: NodeRegistry = load_nodes(['nodes/core', 'nodes/custom'])