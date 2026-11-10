"""Pure formatting and provider-specific API clients. No DB side effects here."""
from __future__ import annotations

import re
from urllib.parse import quote

import httpx


class PublishError(Exception):
    """Local provider configuration or payload error."""


VALID_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
VALID_PROJECT = re.compile(r"^[A-Za-z][A-Za-z0-9_]{1,30}$")


def validate_target(provider: str, config: dict) -> str:
    if provider == "github":
        owner = config.get("github_owner", "")
        repo = config.get("github_repository", "")
        if not VALID_NAME.fullmatch(owner) or not VALID_NAME.fullmatch(repo):
            raise PublishError("Set valid GITHUB_OWNER and GITHUB_REPOSITORY.")
        return f"{owner}/{repo}".lower()

    if provider == "jira":
        base = config.get("jira_base_url", "").rstrip("/")
        key = config.get("jira_project_key", "")
        if not re.fullmatch(r"https://[a-zA-Z0-9-]+\.atlassian\.net", base):
            raise PublishError("JIRA_BASE_URL must be https://YOUR-SITE.atlassian.net")
        if not VALID_PROJECT.fullmatch(key):
            raise PublishError("Set valid JIRA_PROJECT_KEY.")
        return f"{base}/{key.upper()}"

    raise PublishError("Unsupported provider.")


def provenance(project_id: str, backlog_id: str, story_key: str) -> str:
    return (
        f"ReqFlow-Origin: project={project_id}; "
        f"backlog={backlog_id}; story={story_key}"
    )


def story_markdown(
    story: dict,
    criteria: list[dict],
    project_id: str,
    backlog_id: str,
) -> str:
    evidence = ", ".join(story.get("source_requirement_ids", []))
    lines = [
        story.get("story_text", ""),
        "",
        "## Traceability",
        f"- Requirements: {evidence}",
        f'- Epic: {story.get("epic_key", "")}',
        f'- Approval: {story.get("approval_status", "pending")}',
        f'- AI priority recommendation: {story.get("priority_recommendation", "undetermined")}',
        (
            "- Story points: "
            + (
                str(story["story_points"])
                if story.get("story_points") is not None
                else "Unestimated"
            )
        ),
        "",
        "## Acceptance criteria",
    ]
    matches = [
        item for item in criteria
        if item.get("story_key") == story.get("story_key")
    ]
    for item in matches:
        lines.append(
            f'- **{item.get("criterion_key", "")}** '
            f'({item.get("test_type", "functional")}): '
            f'{item.get("criterion_text", "")}'
        )
    if story.get("assumptions"):
        lines.extend([
            "",
            "## Items for review",
            *[f"- {assumption}" for assumption in story["assumptions"]],
        ])
    lines.extend([
        "",
        "---",
        provenance(project_id, backlog_id, story["story_key"]),
    ])
    return "\n".join(lines)


def jira_adf(text: str) -> dict:
    """Convert plain-text story content to Jira Cloud ADF paragraphs."""
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": line or " "}],
            }
            for line in text.splitlines()
        ],
    }


def _jira_issue_type(config: dict) -> dict:
    """Prefer a verified numeric issue-type ID; otherwise use its name."""
    issue_type_id = str(config.get("jira_issue_type_id", "") or "").strip()
    if issue_type_id:
        if not issue_type_id.isdecimal():
            raise PublishError("JIRA_ISSUE_TYPE_ID must be numeric.")
        return {"id": issue_type_id}

    issue_type_name = str(config.get("jira_issue_type", "Task") or "Task").strip()
    if not issue_type_name:
        raise PublishError("JIRA_ISSUE_TYPE must not be empty.")
    return {"name": issue_type_name}


def publish_provider(
    provider: str,
    config: dict,
    story: dict,
    criteria: list[dict],
    project_id: str,
    backlog_id: str,
) -> dict:
    target = validate_target(provider, config)
    marker = provenance(project_id, backlog_id, story["story_key"])
    body = story_markdown(story, criteria, project_id, backlog_id)
    timeout = httpx.Timeout(25.0, connect=7.0)

    if provider == "github":
        token = config.get("github_token", "")
        if not token:
            raise PublishError("GITHUB_TOKEN is missing.")
        owner, repo = target.split("/")
        url = (
            f"https://api.github.com/repos/"
            f"{quote(owner, safe='')}/{quote(repo, safe='')}/issues"
        )
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        payload = {
            "title": f'[{story["story_key"]}] {story["title"]}',
            "body": body,
        }
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        return {
            "external_id": str(data["number"]),
            "external_url": data["html_url"],
            "marker": marker,
        }

    # Jira Cloud requires email/token authentication and, for this project,
    # a reporter account ID. Its required-field metadata was checked separately.
    email = config.get("jira_email", "")
    token = config.get("jira_api_token", "")
    if not email or not token:
        raise PublishError("JIRA_EMAIL or JIRA_API_TOKEN is missing.")

    reporter_id = str(config.get("jira_reporter_account_id", "") or "").strip()
    if not reporter_id:
        raise PublishError(
            "JIRA_REPORTER_ACCOUNT_ID is required for this Jira project. "
            "Retrieve it using GET /rest/api/3/myself."
        )

    site, project_key = target.rsplit("/", 1)
    payload = {
        "fields": {
            "project": {"key": project_key},
            "summary": f'[{story["story_key"]}] {story["title"]}',
            "description": jira_adf(body),
            "issuetype": _jira_issue_type(config),
            "reporter": {"accountId": reporter_id},
        }
    }
    with httpx.Client(
        timeout=timeout,
        follow_redirects=False,
        auth=(email, token),
    ) as client:
        response = client.post(
            f"{site}/rest/api/3/issue",
            json=payload,
            headers={"Accept": "application/json"},
        )

    # Do not obscure the HTTP exception: the caller classifies and records it.
    response.raise_for_status()
    data = response.json()
    return {
        "external_id": data["key"],
        "external_url": f'{site}/browse/{quote(data["key"], safe="")}',
        "marker": marker,
    }
