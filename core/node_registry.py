# core/node_registry.py
# This module handles dynamic loading of node classes from specified directories.
# It allows for easy extension by placing new node implementations in 'nodes/impl' or 'plugins'.

from typing import Dict, List
import os
import importlib.util
import inspect
import logging
from nodes.base.base_node import Base
from nodes.core.market.filters.atrx_filter_node import AtrXFilter
from nodes.core.market.filters.orb_filter_node import OrbFilter

logger = logging.getLogger(__name__)

def load_nodes(directories: List[str]) -> Dict[str, type]:
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
    registry = {}
    for dir_path in directories:
        # Support absolute and relative directories
        if os.path.isabs(dir_path):
            base_dir = dir_path
        else:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', dir_path))
        for root, subdirs, files in os.walk(base_dir):
            # Explicitly import __init__.py if it exists to run extension registrations
            init_path = os.path.join(root, '__init__.py')
            if os.path.exists(init_path):
                # Build module name for __init__.py
                rel_path = os.path.relpath(root, start=os.path.dirname(os.path.dirname(__file__)))
                module_name = rel_path.replace(os.sep, '.')
                if module_name.endswith('.'):  # Handle root package
                    module_name = module_name[:-1]
                spec = importlib.util.spec_from_file_location(module_name, init_path)
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
                    module = importlib.util.module_from_spec(spec)
                    # Adjust package to allow for relative imports within the nodes directory
                    package_name = module_name.split('.')[0]
                    module.__package__ = package_name
                    spec.loader.exec_module(module)
                    for name, obj in vars(module).items():
                        if isinstance(obj, type) and issubclass(obj, Base) and obj != Base and not inspect.isabstract(obj):
                            registry[name] = obj
    return registry

extra_dirs_env = os.getenv('FIG_NODES_PATHS', '')
extra_dirs: List[str] = [p for p in extra_dirs_env.split(':') if p]

NODE_REGISTRY = load_nodes(['nodes/core', 'nodes/custom', *extra_dirs])

# Developer Notes:
# To add a new node:
# 1. Create a new .py file in nodes/core/ or nodes/plugins/.
# 2. Define a class inheriting from Base (or Streaming/UniverseNode).
# 3. Implement required attributes (inputs, outputs, etc.) and execute() method.
# 4. The node will be automatically registered and available in the system.
# 5. For UI parameters, define params_meta list on the class. 
# For extensions in nodes/custom:
# - Add registration code (e.g., register_type) in your subdirectory's __init__.py.
# - It will be auto-imported during loading for seamless integration. 