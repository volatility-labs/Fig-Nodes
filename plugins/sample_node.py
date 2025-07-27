from typing import Dict, Any, List
from nodes.base_node import BaseNode

class SampleCustomNode(BaseNode):
    @property
    def inputs(self) -> List[str]:
        return ['input_data']

    @property
    def outputs(self) -> List[str]:
        return ['output_data']

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        if not self.validate_inputs(inputs):
            raise ValueError(f"Missing inputs for node {self.id}")
        return {'output_data': inputs['input_data'] + '_custom_processed'} 