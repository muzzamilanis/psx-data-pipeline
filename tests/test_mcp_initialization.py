import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from contextlib import asynccontextmanager
import os
import asyncio

@pytest.mark.asyncio
async def test_init_tools():
    """Test MCP tools initialization"""
    
    # Create proper async context manager mocks
    @asynccontextmanager
    async def mock_stdio_client(params):
        read_stream = AsyncMock()
        write_stream = AsyncMock()
        yield (read_stream, write_stream)
    
    @asynccontextmanager
    async def mock_client_session(read, write):
        session = AsyncMock()
        session.initialize = AsyncMock()
        yield session
    
    mock_tools = [MagicMock(name=f"tool_{i}") for i in range(3)]
    mock_toolkit = MagicMock()
    mock_toolkit.get_tools.return_value = mock_tools
    
    # Set environment variables
    test_env = {
        'GOOGLE_OAUTH_CLIENT_ID': 'test_id',
        'GOOGLE_OAUTH_CLIENT_SECRET': 'test_secret',
        'GOOGLE_OAUTH_REFRESH_TOKEN': 'test_token'
    }
    
    with patch.dict(os.environ, test_env):
        with patch('mcp.client.stdio.stdio_client', mock_stdio_client):
            with patch('mcp.ClientSession', mock_client_session):
                with patch('langchain_mcp.MCPToolkit', return_value=mock_toolkit):
                    # Import the async function directly
                    from System_Health_Check_Agent import _init_tools_async
                    
                    # Call the async function
                    google_tools, gmail_tools = await _init_tools_async()
                    
                    # Verify
                    assert len(google_tools) == 3
                    assert all(isinstance(tool, MagicMock) for tool in google_tools)


def test_init_tools_sync():
    """Test synchronous wrapper for MCP initialization"""
    
    test_env = {
        'GOOGLE_OAUTH_CLIENT_ID': 'test_id',
        'GOOGLE_OAUTH_CLIENT_SECRET': 'test_secret',
        'GOOGLE_OAUTH_REFRESH_TOKEN': 'test_token'
    }
    
    # Mock the async function to avoid actual MCP calls
    async def mock_init_async():
        return [MagicMock(name=f"tool_{i}") for i in range(3)], []
    
    with patch.dict(os.environ, test_env):
        with patch('System_Health_Check_Agent._init_tools_async', mock_init_async):
            import System_Health_Check_Agent as agent
            
            # Reset state
            agent._mcp_initialized = False
            agent.google_drive_tools = []
            
            # Run initialization
            agent.initialize_mcp_tools()
            
            # Verify
            assert agent._mcp_initialized is True
            assert len(agent.google_drive_tools) == 3