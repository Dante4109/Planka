"""Shared fixtures and sample data for planka_tools tests."""
from __future__ import annotations

import json
import pytest

# ---------------------------------------------------------------------------
# Canonical IDs used across test modules
# ---------------------------------------------------------------------------
LABEL_OLD_ID = "lbl-old-1"
LABEL_NEW_ID = "lbl-new-1"
GROUP_OLD_ID = "grp-old-1"
GROUP_NEW_ID = "grp-new-1"
FIELD_OLD_ID = "fld-old-1"
FIELD_NEW_ID = "fld-new-1"
LIST_OLD_ID = "list-old-1"
LIST_NEW_ID = "list-new-1"
CARD_OLD_ID = "card-old-1"
CARD_NEW_ID = "card-new-1"
BOARD_SRC_ID = "src-board-1"

# ---------------------------------------------------------------------------
# A complete board export (with cards + labels + custom fields)
# ---------------------------------------------------------------------------
SAMPLE_EXPORT: dict = {
    "board": {"id": BOARD_SRC_ID, "name": "Sample Board"},
    "lists": [
        {"id": LIST_OLD_ID, "name": "Backlog", "position": 65536, "type": "active"},
        {"id": "list-old-sys", "name": None, "position": 1, "type": "archive"},
    ],
    "labels": [
        {"id": LABEL_OLD_ID, "name": "Bug", "color": "red"},
    ],
    "customFieldGroups": [
        {
            "id": GROUP_OLD_ID,
            "name": "Details",
            "position": 65536,
            "createdAt": "2026-01-01T00:00:00Z",
            "updatedAt": None,
            "boardId": BOARD_SRC_ID,
            "cardId": None,
            "baseCustomFieldGroupId": None,
        }
    ],
    "customFields": [
        {
            "id": FIELD_OLD_ID,
            "name": "Priority",
            "position": 65536,
            "showOnFrontOfCard": True,
            "customFieldGroupId": GROUP_OLD_ID,
        }
    ],
    "customFieldValues": [],
    "cards": [
        {
            "id": CARD_OLD_ID,
            "name": "Fix the bug",
            "listId": LIST_OLD_ID,
            "position": 65536,
            "description": "Bug details here",
            "labelIds": [LABEL_OLD_ID],
            "labelNames": ["Bug"],
            "customFieldValues": [
                {
                    "customFieldGroupId": GROUP_OLD_ID,
                    "customFieldId": FIELD_OLD_ID,
                    "content": "High",
                }
            ],
        },
        {
            "id": "card-old-missing-list",
            "name": "Orphan Card",
            "listId": "list-does-not-exist",
            "position": 131072,
            "description": None,
            "labelIds": [],
            "labelNames": [],
            "customFieldValues": [],
        },
    ],
    "cardLabels": [{"cardId": CARD_OLD_ID, "labelId": LABEL_OLD_ID}],
}


@pytest.fixture
def sample_export():
    """Return a deep copy of SAMPLE_EXPORT."""
    import copy
    return copy.deepcopy(SAMPLE_EXPORT)


@pytest.fixture
def export_file(tmp_path, sample_export):
    """Write SAMPLE_EXPORT to a temp JSON file and return its Path."""
    f = tmp_path / "export.json"
    f.write_text(json.dumps(sample_export), encoding="utf-8")
    return f
