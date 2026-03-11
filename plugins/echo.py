"""Echo plugin — minimal example for a factory plugin."""


def register(mcp, config: dict) -> None:
    @mcp.tool()
    def echo(message: str) -> str:
        """Return the message — for testing."""
        return f"echo: {message}"

    @mcp.tool()
    def echo_upper(message: str) -> str:
        """Return the message in uppercase."""
        return f"ECHO: {message.upper()}"
