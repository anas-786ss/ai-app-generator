import os
import logging
from dotenv import load_dotenv
from github import Github, GithubException
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import urllib.parse

logger = logging.getLogger(__name__)

class GitHubClient:
    def __init__(self):
        load_dotenv()  # Ensure .env is loaded here
        GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
        BASE_REPO_OWNER = os.getenv("BASE_REPO_OWNER")
        if not GITHUB_TOKEN:
            raise ValueError("GITHUB_TOKEN environment variable is not set")
        if not BASE_REPO_OWNER:
            raise ValueError("BASE_REPO_OWNER environment variable is not set")
        try:
            self.gh = Github(GITHUB_TOKEN)
            self.user = self.gh.get_user()
            logger.info("GitHub client initialized", extra={"user": self.user.login})
        except GithubException as e:
            logger.error(f"GitHub auth failed: {str(e)}", extra={"status": e.status, "data": e.data})
            raise

    def create_repo_with_files(self, repo_name: str, files: dict, private=False) -> dict:
        """
        Creates repo and uploads files (dict of filename -> content).
        Enables GitHub Pages on main branch / root folder.
        Returns dict with repo_url, commit_sha, pages_url.
        """
        # Sanitize repo name
        repo_name = repo_name.replace(" ", "-").replace("/", "-").replace("\\", "-")
        logger.info(f"Starting repo creation for {repo_name}", extra={"repo_name": repo_name})

        # Get or create repo
        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=8),
            retry=retry_if_exception_type(GithubException),
            reraise=True
        )
        def get_or_create_repo():
            try:
                repo = self.gh.get_repo(f"{self.user.login}/{repo_name}")
                logger.info(f"Repository already exists, skipping creation", extra={"repo_name": repo_name, "repo_url": repo.html_url})
                return repo
            except GithubException as e:
                if e.status == 404:
                    try:
                        repo = self.user.create_repo(name=repo_name, private=private, auto_init=False)  # Disable auto_init
                        logger.info(f"Repository created successfully", extra={"repo_name": repo_name, "repo_url": repo.html_url})
                        return repo
                    except GithubException as e:
                        logger.error(f"Repo creation failed: {str(e)}", extra={"repo_name": repo_name, "status": e.status, "data": e.data})
                        raise
                else:
                    logger.error(f"Unexpected error checking repo existence: {str(e)}", extra={"repo_name": repo_name, "status": e.status, "data": e.data})
                    raise

        repo = get_or_create_repo()

        # Upload files with retry
        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=8),
            retry=retry_if_exception_type(GithubException),
            reraise=True
        )
        def upload_file(path, content):
            try:
                # Check if file exists
                try:
                    existing_file = repo.get_contents(urllib.parse.quote(path), ref="main")
                    repo.update_file(path, f"Update {path}", content, existing_file.sha, branch="main")
                    logger.info(f"Updated file {path} in repo {repo_name}", extra={"repo_name": repo_name, "path": path})
                except GithubException as e:
                    if e.status == 404:
                        # Create initial commit if repo is empty
                        if not list(repo.get_commits()):
                            repo.create_file(path, f"Initial commit: Add {path}", content, branch="main")
                        else:
                            repo.create_file(path, f"Add {path}", content, branch="main")
                        logger.info(f"Created file {path} in repo {repo_name}", extra={"repo_name": repo_name, "path": path})
                    else:
                        logger.error(f"Error checking file {path}: {str(e)}", extra={"repo_name": repo_name, "path": path, "status": e.status, "data": e.data})
                        raise
            except GithubException as e:
                logger.error(f"File upload failed for {path}: {str(e)}", extra={"repo_name": repo_name, "path": path, "status": e.status, "data": e.data})
                raise

        for path, content in files.items():
            upload_file(path, content)

        # Get latest commit SHA
        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=8),
            retry=retry_if_exception_type(GithubException),
            reraise=True
        )
        def get_commit_sha():
            try:
                commit_sha = repo.get_branch("main").commit.sha
                logger.info(f"Retrieved commit SHA: {commit_sha}", extra={"repo_name": repo_name})
                return commit_sha
            except GithubException as e:
                logger.error(f"Failed to get commit SHA: {str(e)}", extra={"repo_name": repo_name, "status": e.status, "data": e.data})
                raise

        commit_sha = get_commit_sha()

        # Enable GitHub Pages with retry
        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=8),
            retry=retry_if_exception_type(GithubException),
            reraise=True
        )
        def enable_pages():
            try:
                repo._requester.requestJsonAndCheck(
                    "POST",
                    f"{repo.url}/pages",
                    input={"source": {"branch": "main", "path": "/"}}
                )
                logger.info(f"Enabled GitHub Pages for {repo_name}", extra={"repo_name": repo_name})
            except GithubException as e:
                logger.warning(f"Failed to enable GitHub Pages: {str(e)}", extra={"repo_name": repo_name, "status": e.status, "data": e.data})

        enable_pages()

        repo_url = repo.html_url
        pages_url = f"https://{BASE_REPO_OWNER}.github.io/{repo_name}/"

        logger.info(f"Repo processed successfully", extra={"repo_url": repo_url, "pages_url": pages_url, "commit_sha": commit_sha})
        return {
            "repo_url": repo_url,
            "commit_sha": commit_sha,
            "pages_url": pages_url
        }
