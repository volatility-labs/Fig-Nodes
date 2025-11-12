from typing import Any

from core.types_registry import NodeCategory, get_type
from nodes.base.base_node import Base


class ImageDisplay(Base):
    """
    Display node for images. Takes images as input and passes them through for display in the UI.

    - Inputs: 'images' -> Dict[str, str] mapping label to data URL
    - Output: 'images' -> Dict[str, str] mapping label to data URL (pass-through)
    """

    inputs = {
        "images": get_type("ConfigDict") | None,
    }

    outputs = {
        "images": get_type("ConfigDict"),
    }

    CATEGORY = NodeCategory.MARKET

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        images = inputs.get("images")
        if images is None:
            return {"images": {}}

        # Pass through images for display
        return {"images": images}
