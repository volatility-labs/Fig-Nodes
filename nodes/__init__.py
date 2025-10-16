# nodes/__init__.py
# This package contains base classes and implementations for graph nodes.
# Submodules:
# - base/: Abstract base classes like Base, Streaming, UniverseNode.
# - core/: Core node implementations organized by domain (io, flow, market, logic, llm).
# - plugins/: External/provider-specific nodes (e.g., binance, polygon, samples).
#
# To create custom nodes, create under nodes/plugins/<your_namespace>/ and they will be auto-discovered. 