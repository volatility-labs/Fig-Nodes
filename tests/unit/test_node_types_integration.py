"""Integration test to verify node type parsing matches frontend expectations"""

from core.node_registry import NODE_REGISTRY  # noqa: F401
from core.types_utils import parse_type


def test_text_to_llm_message_output_type():
    """Verify TextToLLMMessage output type is parsed correctly"""
    from nodes.core.llm.text_to_llm_message_node import TextToLLMMessage
    
    # Get the output type
    output_type = TextToLLMMessage.outputs["message"]
    parsed = parse_type(output_type)
    
    print(f"\n[DEBUG] TextToLLMMessage output type object: {output_type}")
    print(f"[DEBUG] TextToLLMMessage output parsed: {parsed}")
    
    # Should be just LLMChatMessage (non-Optional)
    assert parsed == {"base": "LLMChatMessage"}


def test_llm_messages_builder_input_type():
    """Verify LLMMessagesBuilder input type is parsed correctly"""
    from nodes.core.llm.llm_messages_builder_node import LLMMessagesBuilder
    
    # Get the first input type
    input_type = LLMMessagesBuilder.inputs["message_0"]
    parsed = parse_type(input_type)
    
    print(f"\n[DEBUG] LLMMessagesBuilder input type object: {input_type}")
    print(f"[DEBUG] LLMMessagesBuilder input parsed: {parsed}")
    
    # Should be normalized to just LLMChatMessage (stripped Optional)
    assert parsed == {"base": "LLMChatMessage"}


def test_node_metadata_serialization():
    """Test how node metadata is serialized for the frontend"""
    from core.node_registry import NODE_REGISTRY
    
    # Get TextToLLMMessage metadata
    text_to_llm_cls = NODE_REGISTRY.get("TextToLLMMessage")
    if text_to_llm_cls:
        outputs_meta = {k: parse_type(v) for k, v in text_to_llm_cls.outputs.items()}
        print(f"\n[DEBUG] TextToLLMMessage serialized outputs: {outputs_meta}")
        
        # The "message" output should be just {"base": "LLMChatMessage"}
        assert outputs_meta["message"] == {"base": "LLMChatMessage"}
    
    # Get LLMMessagesBuilder metadata
    llm_builder_cls = NODE_REGISTRY.get("LLMMessagesBuilder")
    if llm_builder_cls:
        inputs_meta = {k: parse_type(v) for k, v in llm_builder_cls.inputs.items()}
        print(f"\n[DEBUG] LLMMessagesBuilder serialized inputs: {inputs_meta}")
        
        # The first message input should be just {"base": "LLMChatMessage"}
        assert inputs_meta["message_0"] == {"base": "LLMChatMessage"}


def test_connection_compatibility():
    """Test that the output of TextToLLMMessage is compatible with LLMMessagesBuilder input"""
    from core.node_registry import NODE_REGISTRY
    
    text_to_llm_cls = NODE_REGISTRY.get("TextToLLMMessage")
    llm_builder_cls = NODE_REGISTRY.get("LLMMessagesBuilder")
    
    if text_to_llm_cls and llm_builder_cls:
        # Parse both types
        output_type = parse_type(text_to_llm_cls.outputs["message"])
        input_type = parse_type(llm_builder_cls.inputs["message_0"])
        
        print(f"\n[DEBUG] Output type: {output_type}")
        print(f"[DEBUG] Input type: {input_type}")
        
        # They should match after normalization
        assert output_type == input_type == {"base": "LLMChatMessage"}
        
        print(f"\n[DEBUG] ✓ Types are compatible!")

