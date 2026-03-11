"""Greet plugin — second test plugin for proxy tests."""


def register(mcp, config: dict) -> None:
    @mcp.tool()
    def greet(name: str) -> str:
        """Greet someone by name."""
        return f"Hello, {name}!"
