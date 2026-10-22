
import json
import os
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


# Find the repository root from this script's location.
ROOT_DIR = Path(__file__).resolve().parent.parent

README_PATH = ROOT_DIR / "README.md"
PROJECT_PATH = ROOT_DIR / "current_project.json"

RECENT_REPO_LIMIT = 5

CURRENT_START = "<!-- CURRENT_PROJECT:START -->"
CURRENT_END = "<!-- CURRENT_PROJECT:END -->"

RECENT_START = "<!-- RECENT_REPOS:START -->"
RECENT_END = "<!-- RECENT_REPOS:END -->"


def read_current_projects():
    """Load manually selected projects from JSON."""
    with PROJECT_PATH.open("r", encoding="utf-8") as file:
        config = json.load(file)

    projects = config.get("projects", [])

    if not projects:
        raise ValueError("Add at least one project to current_project.json.")

    for project in projects:
        required_fields = [
            "name",
            "repository",
            "description",
            "technologies"
        ]

        for field in required_fields:
            if field not in project:
                raise ValueError(
                    f"Project '{project.get('name', 'Unknown')}' "
                    f"is missing field: {field}"
                )

    return projects


def format_current_projects(projects):
    """Generate Markdown for all selected projects."""
    project_sections = []

    for project in projects:
        name = project["name"]
        repository = project["repository"]
        description = project["description"]
        technologies = ", ".join(project["technologies"])

        repository_url = f"https://github.com/{repository}"

        section = (
            f"### [{name}]({repository_url})\n\n"
            f"{description}\n\n"
            f"**Tech stack:** {technologies}"
        )

        project_sections.append(section)

    return "\n\n---\n\n".join(project_sections)


def fetch_recent_repositories(username):
    """Fetch public repositories sorted by most recent push."""
    api_url = (
        f"https://api.github.com/users/{username}/repos"
        "?type=public&sort=pushed&direction=desc&per_page=100"
    )

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-readme-updater"
    }

    # Use the workflow token when available.
    # Local testing can work without a token for public repositories.
    token = os.getenv("GITHUB_TOKEN")

    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(api_url, headers=headers)

    try:
        with urlopen(request, timeout=20) as response:
            repositories = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError) as error:
        raise RuntimeError(
            f"Could not retrieve GitHub repositories: {error}"
        ) from error

    if not isinstance(repositories, list):
        raise ValueError("GitHub API returned an unexpected response.")

    return repositories


def format_current_project(project):
    """Generate Markdown for the selected project."""
    name = project["name"]
    repository = project["repository"]
    description = project["description"]
    technologies = project["technologies"]

    repository_url = f"https://github.com/{repository}"

    tech_list = ", ".join(technologies)

    markdown = (
        f"### [{name}]({repository_url})\n\n"
        f"{description}\n\n"
        f"**Tech stack:** {tech_list}"
    )

    return markdown


def format_recent_repositories(repositories, profile_repo):
    """Generate a list of recently pushed public repositories."""
    # Don't show the profile README repository itself.
    repositories = [
        repo for repo in repositories
        if repo["full_name"].lower() != profile_repo.lower()
    ]

    # Forks can clutter the list, so omit them.
    repositories = [
        repo for repo in repositories
        if not repo.get("fork", False)
    ]

    repositories = repositories[:RECENT_REPO_LIMIT]

    if not repositories:
        return "No recent public repositories found."

    lines = []

    for repo in repositories:
        name = repo["full_name"]
        url = repo["html_url"]
        description = repo.get("description") or "No description provided."

        # Keep each entry on one Markdown line.
        description = " ".join(description.split())
        description = description.replace("|", "\\|")

        pushed_at = repo.get("pushed_at")

        if pushed_at:
            pushed_date = datetime.fromisoformat(
                pushed_at.replace("Z", "+00:00")
            ).strftime("%Y-%m-%d")
        else:
            pushed_date = "Unknown"

        line = (
            f"- [{name}]({url}) — {description} "
            f"(Last push: {pushed_date})"
        )

        lines.append(line)

    return "\n".join(lines)


def replace_section(readme, start_marker, end_marker, new_content):
    """Replace one marked section without changing the rest."""
    if readme.count(start_marker) != 1:
        raise ValueError(f"Expected exactly one {start_marker} marker.")

    if readme.count(end_marker) != 1:
        raise ValueError(f"Expected exactly one {end_marker} marker.")

    start_index = readme.index(start_marker) + len(start_marker)
    end_index = readme.index(end_marker)

    if end_index < start_index:
        raise ValueError("Section markers are in the wrong order.")

    return (
        readme[:start_index]
        + "\n"
        + new_content
        + "\n"
        + readme[end_index:]
    )


def main():
    """Run the README update."""
    username = os.getenv("GITHUB_USERNAME")

    if not username:
        raise ValueError("Set the GITHUB_USERNAME environment variable.")

    profile_repo = os.getenv("GITHUB_REPOSITORY", f"{username}/{username}")

    projects = read_current_projects()
    repositories = fetch_recent_repositories(username)

    current_markdown = format_current_projects(projects)
    recent_markdown = format_recent_repositories(
        repositories,
        profile_repo
    )

    with README_PATH.open("r", encoding="utf-8") as file:
        readme = file.read()

    # Update the current project section.
    readme = replace_section(
        readme,
        CURRENT_START,
        CURRENT_END,
        current_markdown
    )

    # Update the recent repositories section.
    readme = replace_section(
        readme,
        RECENT_START,
        RECENT_END,
        recent_markdown
    )

    with README_PATH.open("w", encoding="utf-8", newline="\n") as file:
        file.write(readme)

    print("README updated successfully.")
    print(f"Selected projects: {len(projects)}")
    print(f"Recent repositories: {RECENT_REPO_LIMIT} maximum")


if __name__ == "__main__":
    main()
