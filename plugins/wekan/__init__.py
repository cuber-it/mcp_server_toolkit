"""Wekan adapter — MCP plugin for Wekan Kanban board REST API.

23 tools covering boards, lists, cards, custom fields, labels, and checklists.

Config keys:
    url: Wekan server URL (required)
    username: Login username (required)
    password: Login password (required)
    default_board: Default board ID (optional)
"""

from __future__ import annotations

from .client import WekanClient
from . import tools


def register(mcp, config: dict) -> None:
    """Register Wekan tools as MCP tools."""
    url = config.get("url")
    if not url:
        raise ValueError("Wekan plugin requires 'url' in config")

    client = WekanClient(
        url=url,
        username=config.get("username", ""),
        password=config.get("password", ""),
        default_board=config.get("default_board"),
    )

    # --- Boards & Lists ---

    @mcp.tool()
    def wekan_list_boards() -> str:
        """List all accessible Wekan boards."""
        return tools.list_boards(client)

    @mcp.tool()
    def wekan_list_lists(board_id: str = "") -> str:
        """List columns (lists) of a board."""
        return tools.list_lists(client, board_id or None)

    @mcp.tool()
    def wekan_list_swimlanes(board_id: str = "") -> str:
        """List swimlanes of a board."""
        return tools.list_swimlanes(client, board_id or None)

    @mcp.tool()
    def wekan_board_summary(board_id: str = "") -> str:
        """Board overview: cards per list, total statistics."""
        return tools.board_summary(client, board_id or None)

    # --- Cards ---

    @mcp.tool()
    def wekan_list_cards(board_id: str = "", list_id: str = "") -> str:
        """List cards of a board or specific list."""
        return tools.list_cards(client, board_id or None, list_id or None)

    @mcp.tool()
    def wekan_get_card(card_id: str, board_id: str = "") -> str:
        """Get details of a single card."""
        return tools.get_card(client, card_id, board_id or None)

    @mcp.tool()
    def wekan_create_card(
        title: str, list_id: str, board_id: str = "",
        description: str = "", swimlane_id: str = "",
    ) -> str:
        """Create a new card in a list."""
        return tools.create_card(
            client, title, list_id, board_id or None, description, swimlane_id or None,
        )

    @mcp.tool()
    def wekan_move_card(card_id: str, to_list_id: str, board_id: str = "", from_list_id: str = "") -> str:
        """Move a card to another list."""
        return tools.move_card(client, card_id, to_list_id, board_id or None, from_list_id or None)

    @mcp.tool()
    def wekan_update_card(
        card_id: str, board_id: str = "", list_id: str = "",
        title: str = "", description: str = "",
    ) -> str:
        """Update card title and/or description."""
        return tools.update_card(
            client, card_id, board_id or None, list_id or None, title or None, description or None,
        )

    @mcp.tool()
    def wekan_delete_card(card_id: str, board_id: str = "", list_id: str = "") -> str:
        """Delete a card."""
        return tools.delete_card(client, card_id, board_id or None, list_id or None)

    # --- Custom Fields ---

    @mcp.tool()
    def wekan_list_custom_fields(board_id: str = "") -> str:
        """List custom fields of a board."""
        return tools.list_custom_fields(client, board_id or None)

    @mcp.tool()
    def wekan_set_card_custom_field(card_id: str, custom_field_id: str, value: str, board_id: str = "") -> str:
        """Set a custom field value on a card."""
        return tools.set_card_custom_field(client, card_id, custom_field_id, value, board_id or None)

    # --- Labels ---

    @mcp.tool()
    def wekan_list_labels(board_id: str = "") -> str:
        """List labels of a board."""
        return tools.list_labels(client, board_id or None)

    @mcp.tool()
    def wekan_set_card_labels(card_id: str, label_ids: str, board_id: str = "") -> str:
        """Set labels on a card (comma-separated IDs, overwrites existing)."""
        return tools.set_card_labels(client, card_id, label_ids, board_id or None)

    # --- Checklists ---

    @mcp.tool()
    def wekan_list_checklists(card_id: str, board_id: str = "") -> str:
        """List checklists of a card."""
        return tools.list_checklists(client, card_id, board_id or None)

    @mcp.tool()
    def wekan_create_checklist(card_id: str, title: str, items: str = "", board_id: str = "") -> str:
        """Create a checklist on a card, optionally with comma-separated items."""
        return tools.create_checklist(client, card_id, title, items, board_id or None)

    @mcp.tool()
    def wekan_set_checklist_item(
        card_id: str, checklist_id: str, item_id: str,
        is_finished: str = "", title: str = "", board_id: str = "",
    ) -> str:
        """Update a checklist item (status and/or title)."""
        return tools.set_checklist_item(
            client, card_id, checklist_id, item_id, is_finished, title, board_id or None,
        )

    @mcp.tool()
    def wekan_delete_checklist(card_id: str, checklist_id: str, board_id: str = "") -> str:
        """Delete a checklist."""
        return tools.delete_checklist(client, card_id, checklist_id, board_id or None)
