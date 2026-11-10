import re
from typing import Any
from langgraph.graph import END, START, StateGraph
from agents.requirements_analysis.ollama_client import chat_json
from agents.story_generation.prompts import (
    epic_prompt, story_prompt, criteria_prompt, estimation_prompt, validation_prompt
)
from agents.story_generation.state import StoryGenerationState

VALID_POINTS = {1, 2, 3, 5, 8, 13}

def _list(data: dict, key: str) -> list:
    value = data.get(key, [])
    return value if isinstance(value, list) else []

def generate_epics(state: StoryGenerationState) -> dict:
    data = chat_json(epic_prompt(state))
    allowed = {r["temporary_id"] for r in state.get("requirements", [])}
    output, seen = [], set()
    for i, item in enumerate(_list(data, "epics"), 1):
        if not isinstance(item, dict):
            continue
        refs = [x for x in item.get("source_requirement_ids", []) if x in allowed]
        if not refs:
            continue
        key = str(item.get("epic_key") or f"EPIC-{i:03d}")
        if key in seen:
            key = f"EPIC-{i:03d}"
        seen.add(key)
        title = str(item.get("title") or f"Requirements group {i}").strip()
        output.append({
            "epic_key": key, "title": title,
            "description": str(item.get("description") or title).strip(),
            "business_value": str(item.get("business_value") or "").strip(),
            "source_requirement_ids": refs,
        })
    covered_epic_reqs = {rid for epic in output for rid in epic["source_requirement_ids"]}
    missing_epic_reqs = [r["temporary_id"] for r in state.get("requirements", []) if r["temporary_id"] not in covered_epic_reqs]
    if output and missing_epic_reqs:
        output.append({"epic_key": "EPIC-REVIEW", "title": "Unassigned validated requirements", "description": "Requirements not assigned by the model; review grouping.", "business_value": "", "source_requirement_ids": missing_epic_reqs})
    if not output:
        # Deterministic fallback: one epic for each requirement type.
        groups = {}
        for req in state.get("requirements", []):
            groups.setdefault(req.get("requirement_type", "functional"), []).append(req["temporary_id"])
        for i, (kind, refs) in enumerate(groups.items(), 1):
            output.append({"epic_key": f"EPIC-{i:03d}", "title": kind.replace("_", " ").title(),
                           "description": f"Deliver validated {kind.replace('_', ' ')} capabilities.",
                           "business_value": "", "source_requirement_ids": refs})
    return {"epics": output}

def generate_stories(state: StoryGenerationState) -> dict:
    data = chat_json(story_prompt(state))
    req_ids = {r["temporary_id"] for r in state.get("requirements", [])}
    epic_keys = {e["epic_key"] for e in state.get("epics", [])}
    stories, seen = [], set()
    for i, item in enumerate(_list(data, "stories"), 1):
        if not isinstance(item, dict):
            continue
        refs = list(dict.fromkeys(x for x in item.get("source_requirement_ids", []) if x in req_ids))
        epic_key = item.get("epic_key")
        if not refs or epic_key not in epic_keys:
            continue
        key = str(item.get("story_key") or f"US-{i:03d}")
        if key in seen:
            key = f"US-{i:03d}"
        seen.add(key)
        story_text = str(item.get("story_text") or "").strip()
        if not re.match(r"(?i)^as a .+,\s*i want .+,\s*so that .+\.$", story_text):
            continue
        stories.append({
            "story_key": key, "epic_key": epic_key,
            "title": str(item.get("title") or key).strip(),
            "story_text": story_text,
            "description": str(item.get("description") or "").strip(),
            "source_requirement_ids": refs,
            "priority_recommendation": item.get("priority_recommendation") if item.get("priority_recommendation") in {"must","should","could"} else "should",
            "priority_rationale": str(item.get("priority_rationale") or "AI recommendation; requires product-owner approval."),
            "assumptions": item.get("assumptions") if isinstance(item.get("assumptions"), list) else [],
            "story_points": None, "estimate_rationale": "",
        })
    from agents.story_generation.quality import topic
    requirement_map = {r["temporary_id"]: r for r in state.get("requirements", [])}
    filtered = []
    for story in stories:
        mismatch = False
        for rid in story["source_requirement_ids"]:
            req = requirement_map[rid]
            if rid.upper().startswith("NFR-"):
                expected = topic(str(req.get("statement", "")) + " " + str(req.get("title", "")))
                actual = topic(story["title"] + " " + story["story_text"])
                if expected and actual != expected:
                    mismatch = True
        if not mismatch:
            filtered.append(story)
    stories = filtered
    if not stories:
        # Safe fallback creates a traceable story per validated requirement.
        epic_for_req = {}
        for epic in state.get("epics", []):
            for rid in epic["source_requirement_ids"]:
                epic_for_req.setdefault(rid, epic["epic_key"])
        for i, req in enumerate(state.get("requirements", []), 1):
            if req["temporary_id"] not in epic_for_req:
                continue
            actor = "authorized user"
            capability = (req.get("statement") or "implement the documented requirement").rstrip(".")
            stories.append({
                "story_key": f"US-{i:03d}", "epic_key": epic_for_req[req["temporary_id"]],
                "title": req.get("title") or req["temporary_id"],
                "story_text": f"As a {actor}, I want {capability[0].lower()+capability[1:]}, so that the documented business requirement is satisfied.",
                "description": req.get("statement", ""),
                "source_requirement_ids": [req["temporary_id"]],
                "priority_recommendation": "should",
                "priority_rationale": "Fallback recommendation; product-owner approval required.",
                "assumptions": ["Actor and benefit wording require product-owner review."],
                "story_points": None, "estimate_rationale": "",
            })
    # Ensure every validated requirement is traceable even when the model only covers a subset.
    covered = {rid for story in stories for rid in story["source_requirement_ids"]}
    epic_for_req = {rid: e["epic_key"] for e in state.get("epics", []) for rid in e["source_requirement_ids"]}
    for req in state.get("requirements", []):
        rid = req["temporary_id"]
        if rid in covered or rid not in epic_for_req:
            continue
        idx = len(stories) + 1
        statement = (req.get("statement") or "implement the documented requirement").rstrip(".")
        stories.append({"story_key": f"US-FALLBACK-{idx:03d}", "epic_key": epic_for_req[rid],
                        "title": (req.get("title") or statement[:90] or rid),
                        "story_text": f"As a product stakeholder, I want the system to satisfy {rid} ({statement.lower()}), so that the documented quality requirement can be verified.",
                        "description": statement, "source_requirement_ids": [rid],
                        "priority_recommendation": "should", "priority_rationale": "AI placeholder; requires PO approval.",
                        "assumptions": ["Actor and business value require product-owner clarification."],
                        "story_points": None, "estimate_rationale": ""})
    return {"stories": stories}

def generate_criteria(state: StoryGenerationState) -> dict:
    data = chat_json(criteria_prompt(state))
    story_keys = {s["story_key"] for s in state.get("stories", [])}
    output = []
    for i, item in enumerate(_list(data, "acceptance_criteria"), 1):
        if not isinstance(item, dict) or item.get("story_key") not in story_keys:
            continue
        text = str(item.get("criterion_text") or "").strip()
        if not re.search(r"(?i)\bgiven\b.+\bwhen\b.+\bthen\b", text):
            continue
        output.append({
            "story_key": item["story_key"], "criterion_key": str(item.get("criterion_key") or f"AC-{i:03d}"),
            "criterion_text": text,
            "test_type": item.get("test_type") if item.get("test_type") in {"functional","security","performance","audit"} else "functional",
        })
    # If the model omits criteria for a story, mark it for review rather than inventing behavior.
    by_story = {x["story_key"] for x in output}
    for story in state.get("stories", []):
        if story["story_key"] not in by_story:
            output.append({
                "story_key": story["story_key"], "criterion_key": f"AC-REVIEW-{story['story_key']}",
                "criterion_text": "Given the requirement and its source evidence have been reviewed, When the product owner confirms the expected behavior, Then acceptance criteria must be finalized before implementation.",
                "test_type": "functional",
            })
    return {"acceptance_criteria": output}

def estimate_and_link(state: StoryGenerationState) -> dict:
    data = chat_json(estimation_prompt(state))
    estimates = {x.get("story_key"): x for x in _list(data, "estimates") if isinstance(x, dict)}
    stories = []
    for story in state.get("stories", []):
        extra = estimates.get(story["story_key"], {})
        points = extra.get("story_points")
        story = dict(story)
        story["story_points"] = points if points in VALID_POINTS else None
        story["estimate_rationale"] = str(extra.get("estimate_rationale") or "Estimate requires team refinement.")
        priority = extra.get("priority_recommendation")
        if priority in {"must","should","could"}:
            story["priority_recommendation"] = priority
            story["priority_rationale"] = str(extra.get("priority_rationale") or "AI recommendation; requires product-owner approval.")
        stories.append(story)
    keys = {s["story_key"] for s in stories}
    dependencies = []
    for item in _list(data, "dependencies"):
        if not isinstance(item, dict):
            continue
        a, b = item.get("story_key"), item.get("depends_on_story_key")
        if a in keys and b in keys and a != b:
            dependencies.append({
                "story_key": a, "depends_on_story_key": b,
                "dependency_type": item.get("dependency_type") if item.get("dependency_type") in {"blocks","relates_to"} else "relates_to",
                "rationale": str(item.get("rationale") or ""),
            })
    # Do not persist obviously reversed prerequisites; flag other issues at quality gate.
    titles = {s["story_key"]: s["title"].lower() for s in stories}
    dependencies = [d for d in dependencies if not (
        d["dependency_type"] == "blocks" and "record" in titles[d["story_key"]]
        and "view" in titles[d["depends_on_story_key"]])]
    return {"stories": stories, "dependencies": dependencies}

def validate_backlog(state: StoryGenerationState) -> dict:
    from agents.story_generation.quality import validate
    return {"validation": validate(state)}

def build_story_graph():
    graph = StateGraph(StoryGenerationState)
    graph.add_node("generate_epics", generate_epics)
    graph.add_node("generate_stories", generate_stories)
    graph.add_node("generate_criteria", generate_criteria)
    graph.add_node("estimate_and_link", estimate_and_link)
    graph.add_node("validate_backlog", validate_backlog)
    graph.add_edge(START, "generate_epics")
    graph.add_edge("generate_epics", "generate_stories")
    graph.add_edge("generate_stories", "generate_criteria")
    graph.add_edge("generate_criteria", "estimate_and_link")
    graph.add_edge("estimate_and_link", "validate_backlog")
    graph.add_edge("validate_backlog", END)
    return graph.compile()

story_generation_graph = build_story_graph()
