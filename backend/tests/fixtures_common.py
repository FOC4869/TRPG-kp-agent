"""Offline authored-state fixtures for CLI language regression checks."""

import copy

from kp_agent.campaign import CampaignDefinition

def build_fixtures(campaign: CampaignDefinition, character: dict) -> dict[str, dict]:
    """Build known progress from fixed outcomes, never random values or tools."""
    start = campaign.initial_state(san=character["san"])

    def step(state: dict, intent: str, target: str, *, passed: bool | None = None,
             item: str | None = None) -> dict:
        proposed = {"action_type": intent, "target_id": target, "item_id": item}
        validated = campaign.validate_plan(proposed, state)
        return campaign.resolve_action(validated, state, passed)["state"]

    failed = step(copy.deepcopy(start), "investigate", "desk", passed=False)
    study_ready = step(copy.deepcopy(start), "investigate", "desk", passed=True)
    study_ready = step(study_ready, "talk", "butler")
    station = step(copy.deepcopy(study_ready), "move", "exit")
    station_located = step(copy.deepcopy(station), "investigate", "locker", passed=True)
    station_ready = step(copy.deepcopy(station_located), "use_item", "locker", item="locker_key")
    station_ready = step(station_ready, "use_item", "archive_gate", item="archive_key")
    archive = step(copy.deepcopy(station_ready), "move", "exit")
    archive_complete = step(copy.deepcopy(archive), "investigate", "ledger", passed=True)
    archive_complete = step(archive_complete, "talk", "scholar")
    archive_complete = step(archive_complete, "use_item", "seal_console", item="seal_token")
    return {
        "study_start": start, "study_failed": failed, "study_ready": study_ready,
        "station_start": station, "station_located": station_located,
        "station_two_routes": station_ready, "archive_start": archive,
        "archive_complete": archive_complete,
    }

def public_context(campaign: CampaignDefinition, state: dict, character: dict) -> dict:
    context = campaign.planning_context(copy.deepcopy(state))
    context["scene"] = campaign.public_context(state)
    context["character"] = copy.deepcopy(character)
    context["character"]["conditions"] = list(state.get("conditions", []))
    context["character"]["san_lost_today"] = state.get("san_lost_today", 0)
    return context
