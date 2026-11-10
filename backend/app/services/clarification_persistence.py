from psycopg.types.json import Jsonb

def insert_revision(cur,project_id,analysis_id,response):
    """Insert finalized snapshot within caller transaction; no approvals copied."""
    settings_model=response["model"]
    cur.execute("""INSERT INTO backlog_runs(project_id, analysis_run_id, model_name, result)
                   VALUES (%s,%s,%s,%s) RETURNING id, created_at""",
                (project_id, analysis_id, settings_model, Jsonb(response)))
    backlog_id, created_at = cur.fetchone()
    epic_ids = {}
    for epic in response["epics"]:
        cur.execute("""INSERT INTO epics(backlog_run_id, epic_key, title, description, business_value, source_requirement_ids)
                       VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""",
                    (backlog_id, epic["epic_key"], epic["title"], epic["description"], epic.get("business_value", ""), Jsonb(epic["source_requirement_ids"])))
        epic_ids[epic["epic_key"]] = cur.fetchone()[0]
    story_ids = {}
    for story in response["stories"]:
        epic_id = epic_ids.get(story["epic_key"])
        if not epic_id:
            continue
        cur.execute("""INSERT INTO user_stories(backlog_run_id, epic_id, story_key, title, story_text, description,
                       source_requirement_ids, priority_recommendation, priority_rationale, story_points,
                       estimate_rationale, assumptions)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                    (backlog_id, epic_id, story["story_key"], story["title"], story["story_text"], story.get("description", ""),
                     Jsonb(story["source_requirement_ids"]), story["priority_recommendation"], story["priority_rationale"],
                     story.get("story_points"), story.get("estimate_rationale", ""), Jsonb(story.get("assumptions", []))))
        story_ids[story["story_key"]] = cur.fetchone()[0]
    for criterion in response["acceptance_criteria"]:
        story_id = story_ids.get(criterion["story_key"])
        if story_id:
            cur.execute("""INSERT INTO acceptance_criteria(user_story_id, criterion_key, criterion_text, test_type)
                           VALUES (%s,%s,%s,%s)""",
                        (story_id, criterion["criterion_key"], criterion["criterion_text"], criterion["test_type"]))
    for dependency in response["dependencies"]:
        story_id = story_ids.get(dependency["story_key"])
        depends_id = story_ids.get(dependency["depends_on_story_key"])
        if story_id and depends_id:
            cur.execute("""INSERT INTO story_dependencies(backlog_run_id, story_id, depends_on_story_id, dependency_type, rationale)
                           VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                        (backlog_id, story_id, depends_id, dependency["dependency_type"], dependency.get("rationale", "")))
    return backlog_id, created_at
