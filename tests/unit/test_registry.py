import pytest
from typing import Dict, Any, List, Optional
from unittest.mock import AsyncMock, MagicMock
import asyncio

from services.tools.registry import (
    register_tool_schema,
    get_tool_schema,
    list_tool_names,
    list_tool_schemas,
    register_tool_handler,
    get_tool_handler,
    register_tool_factory,
    get_tool_factory,
    register_credential_provider,
    get_credential_provider,
    get_credential,
    get_all_credential_providers,
    ToolHandler,
    get_credential_from_context,
    register_tool_object,
    _TOOL_SCHEMAS,
    _TOOL_HANDLERS,
    _TOOL_FACTORIES,
    _CREDENTIAL_PROVIDERS,
)


class TestToolSchemaRegistry:
    """Tests for tool schema registration and retrieval."""

    def setup_method(self):
        """Clear registries before each test."""
        _TOOL_SCHEMAS.clear()
        _TOOL_HANDLERS.clear()
        _TOOL_FACTORIES.clear()
        _CREDENTIAL_PROVIDERS.clear()

    def test_register_tool_schema_success(self):
        """Test successful schema registration."""
        schema = {"type": "function", "function": {"name": "test_tool"}}
        register_tool_schema("test_tool", schema)

        assert "test_tool" in _TOOL_SCHEMAS
        assert _TOOL_SCHEMAS["test_tool"] == schema

    def test_register_tool_schema_invalid_name(self):
        """Test schema registration with invalid names."""
        schema = {"type": "function"}

        with pytest.raises(ValueError, match="Tool schema name must be a non-empty string"):
            register_tool_schema("", schema)

        with pytest.raises(ValueError, match="Tool schema name must be a non-empty string"):
            register_tool_schema(None, schema)

        with pytest.raises(ValueError, match="Tool schema name must be a non-empty string"):
            register_tool_schema(123, schema)

    def test_register_tool_schema_invalid_schema(self):
        """Test schema registration with invalid schemas."""
        with pytest.raises(ValueError, match="Tool schema must be a non-empty dict"):
            register_tool_schema("test_tool", {})

        with pytest.raises(ValueError, match="Tool schema must be a non-empty dict"):
            register_tool_schema("test_tool", None)

        with pytest.raises(ValueError, match="Tool schema must be a non-empty dict"):
            register_tool_schema("test_tool", "not_a_dict")

    def test_get_tool_schema_existing(self):
        """Test retrieving existing schema."""
        schema = {"type": "function", "function": {"name": "test_tool"}}
        register_tool_schema("test_tool", schema)

        result = get_tool_schema("test_tool")
        assert result == schema

    def test_get_tool_schema_nonexistent(self):
        """Test retrieving non-existent schema."""
        result = get_tool_schema("nonexistent")
        assert result is None

    def test_list_tool_names_empty(self):
        """Test listing tool names when empty."""
        assert list_tool_names() == []

    def test_list_tool_names_with_tools(self):
        """Test listing tool names with registered tools."""
        register_tool_schema("tool_c", {"type": "function"})
        register_tool_schema("tool_a", {"type": "function"})
        register_tool_schema("tool_b", {"type": "function"})

        names = list_tool_names()
        assert names == ["tool_a", "tool_b", "tool_c"]  # Should be sorted

    def test_list_tool_schemas_empty(self):
        """Test listing schemas when empty."""
        assert list_tool_schemas() == []

    def test_list_tool_schemas_with_tools(self):
        """Test listing schemas with registered tools."""
        schema1 = {"type": "function", "function": {"name": "tool_a"}}
        schema2 = {"type": "function", "function": {"name": "tool_b"}}

        register_tool_schema("tool_a", schema1)
        register_tool_schema("tool_b", schema2)

        schemas = list_tool_schemas()
        assert len(schemas) == 2
        assert schema1 in schemas
        assert schema2 in schemas


class TestToolHandlerRegistry:
    """Tests for tool handler registration and retrieval."""

    def setup_method(self):
        """Clear registries before each test."""
        _TOOL_SCHEMAS.clear()
        _TOOL_HANDLERS.clear()
        _TOOL_FACTORIES.clear()
        _CREDENTIAL_PROVIDERS.clear()

    @pytest.mark.asyncio
    async def test_register_tool_handler_success(self):
        """Test successful handler registration."""
        async def test_handler(arguments, context):
            return "result"

        register_tool_handler("test_handler", test_handler)

        assert "test_handler" in _TOOL_HANDLERS
        assert _TOOL_HANDLERS["test_handler"] == test_handler

        # Test the handler works
        result = await _TOOL_HANDLERS["test_handler"]({}, {})
        assert result == "result"

    def test_register_tool_handler_invalid_name(self):
        """Test handler registration with invalid names."""
        async def handler(args, context):
            return None

        with pytest.raises(ValueError, match="Tool handler name must be a non-empty string"):
            register_tool_handler("", handler)

        with pytest.raises(ValueError, match="Tool handler name must be a non-empty string"):
            register_tool_handler(None, handler)

    def test_register_tool_handler_invalid_handler(self):
        """Test handler registration with invalid handlers."""
        with pytest.raises(ValueError, match="Tool handler must be callable"):
            register_tool_handler("test", None)

        with pytest.raises(ValueError, match="Tool handler must be callable"):
            register_tool_handler("test", "not_callable")

    def test_get_tool_handler_existing(self):
        """Test retrieving existing handler."""
        async def test_handler(arguments, context):
            return "result"

        register_tool_handler("test_handler", test_handler)
        result = get_tool_handler("test_handler")
        assert result == test_handler

    def test_get_tool_handler_nonexistent(self):
        """Test retrieving non-existent handler."""
        result = get_tool_handler("nonexistent")
        assert result is None


class TestToolFactoryRegistry:
    """Tests for tool factory registration and retrieval."""

    def setup_method(self):
        """Clear registries before each test."""
        _TOOL_SCHEMAS.clear()
        _TOOL_HANDLERS.clear()
        _TOOL_FACTORIES.clear()
        _CREDENTIAL_PROVIDERS.clear()

    def test_register_tool_factory_success(self):
        """Test successful factory registration."""
        class MockTool(ToolHandler):
            @property
            def name(self):
                return "mock_tool"

            def schema(self):
                return {"type": "function", "function": {"name": self.name}}

            async def execute(self, arguments, context):
                return "mock_result"

        def factory():
            return MockTool()

        register_tool_factory("mock_tool", factory)

        assert "mock_tool" in _TOOL_FACTORIES
        assert _TOOL_FACTORIES["mock_tool"] == factory

        # Should also register schema and handler
        assert "mock_tool" in _TOOL_SCHEMAS
        assert "mock_tool" in _TOOL_HANDLERS

    def test_register_tool_factory_invalid_name(self):
        """Test factory registration with invalid names."""
        def factory():
            return None

        with pytest.raises(ValueError, match="Tool factory name must be a non-empty string"):
            register_tool_factory("", factory)

    def test_register_tool_factory_invalid_factory(self):
        """Test factory registration with invalid factories."""
        with pytest.raises(ValueError, match="Tool factory must be callable"):
            register_tool_factory("test", None)

    def test_register_tool_factory_failing_factory(self):
        """Test factory registration when factory fails during schema extraction."""
        def failing_factory():
            raise RuntimeError("Factory failure")

        # Should not raise, should just skip schema registration
        register_tool_factory("failing_tool", failing_factory)
        assert "failing_tool" in _TOOL_FACTORIES
        # Schema should not be registered due to failure
        assert "failing_tool" not in _TOOL_SCHEMAS

    def test_get_tool_factory_existing(self):
        """Test retrieving existing factory."""
        def factory():
            return None

        register_tool_factory("test_factory", factory)
        result = get_tool_factory("test_factory")
        assert result == factory

    def test_get_tool_factory_nonexistent(self):
        """Test retrieving non-existent factory."""
        result = get_tool_factory("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_factory_created_handler(self):
        """Test that factory-created handlers work."""
        class MockTool(ToolHandler):
            @property
            def name(self):
                return "factory_tool"

            def schema(self):
                return {"type": "function", "function": {"name": self.name}}

            async def execute(self, arguments, context):
                return f"executed_{arguments.get('test', 'default')}"

        def factory():
            return MockTool()

        register_tool_factory("factory_tool", factory)

        # Get the auto-created handler
        handler = get_tool_handler("factory_tool")
        assert handler is not None

        # Test the handler
        result = await handler({"test": "value"}, {})
        assert result == "executed_value"


class TestCredentialProviderRegistry:
    """Tests for credential provider registration and retrieval."""

    def setup_method(self):
        """Clear registries before each test."""
        _TOOL_SCHEMAS.clear()
        _TOOL_HANDLERS.clear()
        _TOOL_FACTORIES.clear()
        _CREDENTIAL_PROVIDERS.clear()

    def test_register_credential_provider_success(self):
        """Test successful credential provider registration."""
        def provider():
            return "secret_key"

        register_credential_provider("api_key", provider)

        assert "api_key" in _CREDENTIAL_PROVIDERS
        assert _CREDENTIAL_PROVIDERS["api_key"] == provider

    def test_register_credential_provider_invalid_name(self):
        """Test credential provider registration with invalid names."""
        def provider():
            return "key"

        with pytest.raises(ValueError, match="Credential provider name must be a non-empty string"):
            register_credential_provider("", provider)

    def test_register_credential_provider_invalid_provider(self):
        """Test credential provider registration with invalid providers."""
        with pytest.raises(ValueError, match="Credential provider must be callable"):
            register_credential_provider("test", None)

    def test_get_credential_provider_existing(self):
        """Test retrieving existing credential provider."""
        def provider():
            return "secret"

        register_credential_provider("test_cred", provider)
        result = get_credential_provider("test_cred")
        assert result == provider

    def test_get_credential_provider_nonexistent(self):
        """Test retrieving non-existent credential provider."""
        result = get_credential_provider("nonexistent")
        assert result is None

    def test_get_credential_success(self):
        """Test successful credential retrieval."""
        def provider():
            return "my_secret_key"

        register_credential_provider("test_cred", provider)
        result = get_credential("test_cred")
        assert result == "my_secret_key"

    def test_get_credential_nonexistent(self):
        """Test credential retrieval for non-existent provider."""
        result = get_credential("nonexistent")
        assert result is None

    def test_get_credential_provider_failure(self):
        """Test credential retrieval when provider fails."""
        def failing_provider():
            raise RuntimeError("Provider failed")

        register_credential_provider("failing_cred", failing_provider)
        result = get_credential("failing_cred")
        assert result is None

    def test_get_all_credential_providers(self):
        """Test getting all credential providers."""
        def provider1():
            return "key1"

        def provider2():
            return "key2"

        register_credential_provider("cred1", provider1)
        register_credential_provider("cred2", provider2)

        all_providers = get_all_credential_providers()
        assert len(all_providers) == 2
        assert all_providers["cred1"] == provider1
        assert all_providers["cred2"] == provider2

        # Should return a copy, not the original dict
        assert all_providers is not _CREDENTIAL_PROVIDERS


class TestToolHandlerInterface:
    """Tests for the ToolHandler abstract base class."""

    def test_tool_handler_is_abstract(self):
        """Test that ToolHandler cannot be instantiated directly."""
        with pytest.raises(TypeError):
            ToolHandler()

    def test_tool_handler_subclass(self):
        """Test creating a valid ToolHandler subclass."""
        class ValidTool(ToolHandler):
            @property
            def name(self):
                return "valid_tool"

            def schema(self):
                return {"type": "function", "function": {"name": self.name}}

            async def execute(self, arguments, context):
                return "result"

        tool = ValidTool()
        assert tool.name == "valid_tool"
        assert tool.schema() == {"type": "function", "function": {"name": "valid_tool"}}

        # Test async execution
        async def test_execute():
            result = await tool.execute({}, {})
            assert result == "result"

        asyncio.run(test_execute())


class TestCredentialFromContext:
    """Tests for get_credential_from_context helper function."""

    def test_get_credential_from_context_success(self):
        """Test successful credential retrieval from context."""
        def provider():
            return "context_secret"

        context = {
            "credentials": {
                "api_key": provider
            }
        }

        result = get_credential_from_context(context, "api_key")
        assert result == "context_secret"

    def test_get_credential_from_context_no_credentials(self):
        """Test credential retrieval when no credentials in context."""
        context = {}
        result = get_credential_from_context(context, "api_key")
        assert result is None

    def test_get_credential_from_context_no_matching_credential(self):
        """Test credential retrieval when credential doesn't exist."""
        context = {
            "credentials": {
                "other_key": lambda: "other"
            }
        }
        result = get_credential_from_context(context, "api_key")
        assert result is None

    def test_get_credential_from_context_non_callable_provider(self):
        """Test credential retrieval when provider is not callable."""
        context = {
            "credentials": {
                "api_key": "not_callable"
            }
        }
        result = get_credential_from_context(context, "api_key")
        assert result is None

    def test_get_credential_from_context_provider_failure(self):
        """Test credential retrieval when provider fails."""
        def failing_provider():
            raise ValueError("Provider failed")

        context = {
            "credentials": {
                "api_key": failing_provider
            }
        }
        result = get_credential_from_context(context, "api_key")
        assert result is None

    def test_get_credential_from_context_invalid_credentials_type(self):
        """Test credential retrieval when credentials is not a dict."""
        context = {
            "credentials": "not_a_dict"
        }
        result = get_credential_from_context(context, "api_key")
        assert result is None


class TestRegisterToolObject:
    """Tests for register_tool_object function."""

    def setup_method(self):
        """Clear registries before each test."""
        _TOOL_SCHEMAS.clear()
        _TOOL_HANDLERS.clear()
        _TOOL_FACTORIES.clear()
        _CREDENTIAL_PROVIDERS.clear()

    def test_register_tool_object_success(self):
        """Test successful tool object registration."""
        class TestTool(ToolHandler):
            @property
            def name(self):
                return "test_tool"

            def schema(self):
                return {"type": "function", "function": {"name": self.name}}

            async def execute(self, arguments, context):
                return "tool_result"

        tool = TestTool()
        register_tool_object(tool)

        # Should register schema and handler
        assert "test_tool" in _TOOL_SCHEMAS
        assert "test_tool" in _TOOL_HANDLERS

        # Test the registered handler
        async def test_handler():
            handler = get_tool_handler("test_tool")
            result = await handler({}, {})
            assert result == "tool_result"

        asyncio.run(test_handler())


class TestRegistryIntegration:
    """Integration tests for registry functionality."""

    def setup_method(self):
        """Clear registries before each test."""
        _TOOL_SCHEMAS.clear()
        _TOOL_HANDLERS.clear()
        _TOOL_FACTORIES.clear()
        _CREDENTIAL_PROVIDERS.clear()

    def test_complete_tool_registration_workflow(self):
        """Test a complete tool registration and usage workflow."""
        # Register schema
        schema = {"type": "function", "function": {"name": "workflow_tool"}}
        register_tool_schema("workflow_tool", schema)

        # Register handler
        async def handler(arguments, context):
            return f"processed_{arguments.get('input', 'default')}"

        register_tool_handler("workflow_tool", handler)

        # Register credential provider
        def cred_provider():
            return "workflow_secret"

        register_credential_provider("workflow_api_key", cred_provider)

        # Verify everything is registered
        assert get_tool_schema("workflow_tool") == schema
        assert get_tool_handler("workflow_tool") == handler
        assert get_credential("workflow_api_key") == "workflow_secret"

        # Test tool names listing
        names = list_tool_names()
        assert "workflow_tool" in names

        # Test schemas listing
        schemas = list_tool_schemas()
        assert schema in schemas

    def test_registry_state_isolation(self):
        """Test that registry state is properly isolated between tests."""
        # This test should pass because setup_method clears registries
        assert len(_TOOL_SCHEMAS) == 0
        assert len(_TOOL_HANDLERS) == 0
        assert len(_TOOL_FACTORIES) == 0
        assert len(_CREDENTIAL_PROVIDERS) == 0

        # Add something
        register_tool_schema("isolation_test", {"type": "test"})

        # Verify it's there
        assert "isolation_test" in _TOOL_SCHEMAS

        # Next test should have clean state due to setup_method
