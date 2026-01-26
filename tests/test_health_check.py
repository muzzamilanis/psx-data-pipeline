import pytest
import asyncio

@pytest.mark.asyncio
async def test_health_check():
    async def async_generator():
        yield "test"

    async for value in async_generator():
        assert value == "test"