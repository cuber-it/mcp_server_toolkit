"""Wekan tool functions — pure Python, no MCP dependency.

Each function takes a WekanClient and returns a formatted string.
Covers boards, lists, cards, custom fields, labels, and checklists.
"""

from __future__ import annotations

import json
from typing import Any

from .client import WekanClient


def _fmt(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


# --- Boards & Lists ---

def list_boards(client: WekanClient) -> str:
    boards = client.get("/boards")
    result = [{"id": b["_id"], "title": b.get("title", "?")} for b in boards if not b.get("archived")]
    return _fmt(result)


def list_lists(client: WekanClient, board_id: str | None = None) -> str:
    bid = client._bid(board_id)
    lists = client.get(f"/boards/{bid}/lists")
    return _fmt([{"id": l["_id"], "title": l.get("title", "?")} for l in lists])


def list_swimlanes(client: WekanClient, board_id: str | None = None) -> str:
    bid = client._bid(board_id)
    swimlanes = client.get(f"/boards/{bid}/swimlanes")
    return _fmt([{"id": s["_id"], "title": s.get("title", "?")} for s in swimlanes])


# --- Cards ---

def list_cards(client: WekanClient, board_id: str | None = None, list_id: str | None = None) -> str:
    bid = client._bid(board_id)
    if list_id:
        cards = client.get(f"/boards/{bid}/lists/{list_id}/cards")
    else:
        lists = client.get(f"/boards/{bid}/lists")
        cards = []
        for lst in lists:
            lid = lst["_id"]
            list_cards = client.get(f"/boards/{bid}/lists/{lid}/cards")
            for c in list_cards:
                c["list_title"] = lst.get("title", "?")
            cards.extend(list_cards)
    result = [
        {"id": c["_id"], "title": c.get("title", "?"), "list": c.get("list_title", "")}
        for c in cards
    ]
    return _fmt(result)


def get_card(client: WekanClient, card_id: str, board_id: str | None = None) -> str:
    bid = client._bid(board_id)
    lists = client.get(f"/boards/{bid}/lists")
    for lst in lists:
        try:
            card = client.get(f"/boards/{bid}/lists/{lst['_id']}/cards/{card_id}")
            if card:
                return _fmt(card)
        except Exception:
            continue
    return _fmt({"error": f"Card {card_id} not found"})


def board_summary(client: WekanClient, board_id: str | None = None) -> str:
    bid = client._bid(board_id)
    lists = client.get(f"/boards/{bid}/lists")
    total = 0
    summary = []
    for lst in lists:
        cards = client.get(f"/boards/{bid}/lists/{lst['_id']}/cards")
        count = len(cards)
        total += count
        summary.append({
            "list": lst.get("title", "?"),
            "cards": count,
            "titles": [c.get("title", "?") for c in cards],
        })
    return _fmt({"total_cards": total, "lists": summary})


def create_card(
    client: WekanClient, title: str, list_id: str,
    board_id: str | None = None, description: str = "", swimlane_id: str | None = None,
) -> str:
    bid = client._bid(board_id)
    if not swimlane_id:
        swimlanes = client.get(f"/boards/{bid}/swimlanes")
        swimlane_id = swimlanes[0]["_id"] if swimlanes else None
    payload = {
        "title": title, "description": description,
        "authorId": client._user_id, "swimlaneId": swimlane_id,
    }
    result = client.post(f"/boards/{bid}/lists/{list_id}/cards", data=payload)
    return _fmt(result)


def move_card(
    client: WekanClient, card_id: str, to_list_id: str,
    board_id: str | None = None, from_list_id: str | None = None,
) -> str:
    bid = client._bid(board_id)
    if not from_list_id:
        from_list_id = _find_card_list(client, bid, card_id)
    result = client.put(
        f"/boards/{bid}/lists/{from_list_id}/cards/{card_id}",
        data={"listId": to_list_id},
    )
    return _fmt({"status": "moved", "card_id": card_id, "to_list": to_list_id})


def update_card(
    client: WekanClient, card_id: str, board_id: str | None = None,
    list_id: str | None = None, title: str | None = None, description: str | None = None,
) -> str:
    bid = client._bid(board_id)
    if not list_id:
        list_id = _find_card_list(client, bid, card_id)
    payload = {}
    if title:
        payload["title"] = title
    if description is not None:
        payload["description"] = description
    if not payload:
        return _fmt({"status": "nothing_to_update"})
    client.put(f"/boards/{bid}/lists/{list_id}/cards/{card_id}", data=payload)
    return _fmt({"status": "updated", "card_id": card_id})


def delete_card(
    client: WekanClient, card_id: str, board_id: str | None = None, list_id: str | None = None,
) -> str:
    bid = client._bid(board_id)
    if not list_id:
        list_id = _find_card_list(client, bid, card_id)
    client.delete(f"/boards/{bid}/lists/{list_id}/cards/{card_id}")
    return _fmt({"status": "deleted", "card_id": card_id})


# --- Custom Fields ---

def list_custom_fields(client: WekanClient, board_id: str | None = None) -> str:
    bid = client._bid(board_id)
    return _fmt(client.get(f"/boards/{bid}/custom-fields"))


def set_card_custom_field(
    client: WekanClient, card_id: str, custom_field_id: str, value: str,
    board_id: str | None = None,
) -> str:
    bid = client._bid(board_id)
    client.put(f"/boards/{bid}/cards/{card_id}/customField/{custom_field_id}", data={"value": value})
    return _fmt({"status": "updated", "card_id": card_id, "field": custom_field_id})


# --- Labels ---

def list_labels(client: WekanClient, board_id: str | None = None) -> str:
    bid = client._bid(board_id)
    board = client.get(f"/boards/{bid}")
    return _fmt(board.get("labels", []))


def set_card_labels(
    client: WekanClient, card_id: str, label_ids: str, board_id: str | None = None,
) -> str:
    bid = client._bid(board_id)
    list_id = _find_card_list(client, bid, card_id)
    ids = [lid.strip() for lid in label_ids.split(",") if lid.strip()]
    client.put(f"/boards/{bid}/lists/{list_id}/cards/{card_id}", data={"labelIds": ids})
    return _fmt({"status": "updated", "card_id": card_id, "labels": ids})


# --- Checklists ---

def list_checklists(client: WekanClient, card_id: str, board_id: str | None = None) -> str:
    bid = client._bid(board_id)
    return _fmt(client.get(f"/boards/{bid}/cards/{card_id}/checklists"))


def create_checklist(
    client: WekanClient, card_id: str, title: str, items: str = "",
    board_id: str | None = None,
) -> str:
    bid = client._bid(board_id)
    payload = {"title": title}
    if items:
        payload["items"] = [i.strip() for i in items.split(",") if i.strip()]
    return _fmt(client.post(f"/boards/{bid}/cards/{card_id}/checklists", data=payload))


def set_checklist_item(
    client: WekanClient, card_id: str, checklist_id: str, item_id: str,
    is_finished: str = "", title: str = "", board_id: str | None = None,
) -> str:
    bid = client._bid(board_id)
    payload = {}
    if is_finished.lower() in ("true", "false"):
        payload["isFinished"] = is_finished.lower() == "true"
    if title:
        payload["title"] = title
    if not payload:
        return _fmt({"status": "nothing_to_update"})
    client.put(
        f"/boards/{bid}/cards/{card_id}/checklists/{checklist_id}/items/{item_id}",
        data=payload,
    )
    return _fmt({"status": "updated", "item_id": item_id})


def delete_checklist(
    client: WekanClient, card_id: str, checklist_id: str, board_id: str | None = None,
) -> str:
    bid = client._bid(board_id)
    client.delete(f"/boards/{bid}/cards/{card_id}/checklists/{checklist_id}")
    return _fmt({"status": "deleted", "checklist_id": checklist_id})


# --- Helpers ---

def _find_card_list(client: WekanClient, board_id: str, card_id: str) -> str:
    lists = client.get(f"/boards/{board_id}/lists")
    for lst in lists:
        try:
            card = client.get(f"/boards/{board_id}/lists/{lst['_id']}/cards/{card_id}")
            if card:
                return lst["_id"]
        except Exception:
            continue
    raise ValueError(f"Card {card_id} not found in board {board_id}")
