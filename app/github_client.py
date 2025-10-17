import os
from github import Github, GithubException
from app.utils import setup_logging

logger = setup_logging()

def create_or_update_repo(repo_name: str, code: str, checks: list, round: int) -> tuple:
    try:
        github_token = os.getenv("GITHUB_TOKEN")
        base_repo_owner = os.getenv("BASE_REPO_OWNER")
        if not github_token or not base_repo_owner:
            logger.error("Missing GITHUB_TOKEN or BASE_REPO_OWNER")
            raise ValueError("GitHub configuration missing")
        
        g = Github(github_token)
        user = g.get_user()
        
        try:
            repo = user.get_repo(repo_name)
            logger.info(f"Repository {repo_name} found, updating for round {round}")
        except GithubException:
            logger.info(f"Creating new repository {repo_name}")
            repo = user.create_repo(repo_name, auto_init=True, license_template="mit")
        
        files = {
            "index.html": code,
            "README.md": f"# {repo_name}\n\nBrief: {repo_name}\n\nChecks:\n" + "\n".join(f"- {check}" for check in checks),
            "LICENSE": repo.get_license().decoded_content.decode() if repo.get_license() else "MIT License\n\n..."
        }
        
        for file_path, content in files.items():
            try:
                file = repo.get_contents(file_path)
                repo.update_file(file_path, f"Update {file_path} for round {round}", content, file.sha)
                logger.info(f"Updated {file_path} in {repo_name}")
            except GithubException:
                repo.create_file(file_path, f"Create {file_path} for round {round}", content)
                logger.info(f"Created {file_path} in {repo_name}")
        
        try:
            # Enable GitHub Pages
            repo.create_source_branch("main")
            repo.enable_pages(branch="main", path="/")
            logger.info(f"Enabled GitHub Pages for {repo_name}")
        except GithubException as e:
            logger.warning(f"Failed to enable GitHub Pages: {str(e)}")
        
        commit_sha = repo.get_commits()[0].sha
        pages_url = f"https://{base_repo_owner.lower()}.github.io/{repo_name}/"
        
        return repo.html_url, commit_sha, pages_url
    except Exception as e:
        logger.error(f"Error in create_or_update_repo: {str(e)}")
        raise
