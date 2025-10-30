"""Note node - a visual annotation element on the canvas."""

from typing import Any

from core.types_registry import NodeCategory, ParamMeta
from nodes.base.base_node import Base


class Note(Base):
    """A visual note/annotation node for organizing and labeling groups of nodes.

    This node provides no functionality - it's purely visual. It renders as a
    colored rectangle with editable text content that can be used to visually
    group and annotate other nodes on the canvas.
    """

    inputs = {}
    outputs = {}
    CATEGORY: NodeCategory = NodeCategory.IO

    params_meta: list[ParamMeta] = [
        {
            "name": "text",
            "type": "textarea",
            "default": "Note",
        },
        {
            "name": "color",
            "type": "text",
            "default": "#334",
        },
    ]

    default_params = {
        "text": "Note",
        "color": "#334",
    }

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Note node provides no execution - it's purely visual."""
        return {}
