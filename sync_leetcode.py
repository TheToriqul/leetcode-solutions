import os
import requests
from github import Github
from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional
import time
from functools import wraps

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LeetCodeGitHubSync:
    # Language to file extension mapping
    EXTENSIONS = {
        'python': 'py', 'python3': 'py', 'java': 'java',
        'cpp': 'cpp', 'c++': 'cpp', 'javascript': 'js',
        'typescript': 'ts', 'golang': 'go', 'ruby': 'rb',
        'swift': 'swift', 'kotlin': 'kt', 'rust': 'rs',
        'scala': 'scala', 'php': 'php'
    }

    # API endpoints
    LEETCODE_GRAPHQL_URL = "https://leetcode.com/graphql"
    LEETCODE_SUBMISSIONS_URL = "https://leetcode.com/api/submissions/"

    def __init__(self, github_token: str, github_repo: str, leetcode_session: str):
        """
        Initialize the LeetCode-GitHub sync tool with necessary credentials.
        
        Args:
            github_token: GitHub Personal Access Token
            github_repo: GitHub repository name (format: "username/repo")
            leetcode_session: LeetCode session cookie
        """
        if not all([github_token, github_repo, leetcode_session]):
            raise ValueError("Missing required credentials")

        self.github = Github(github_token)
        self.repo = self.github.get_repo(github_repo)
        self.headers = {
            'Cookie': f'LEETCODE_SESSION={leetcode_session}',
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://leetcode.com'
        }
        # Cache for existing files and folders
        self.path_cache = set()
        self._init_path_cache()

    def _init_path_cache(self):
        """Initialize cache of existing paths in the repository."""
        try:
            contents = self.repo.get_contents("")
            while contents:
                file_content = contents.pop(0)
                self.path_cache.add(file_content.path)
                if file_content.type == "dir":
                    contents.extend(self.repo.get_contents(file_content.path))
        except Exception as e:
            logger.error(f"Error initializing path cache: {str(e)}")

    def retry_with_backoff(retries=3, backoff_in_seconds=1):
        """Decorator for implementing retry logic with exponential backoff."""
        def decorator(func):
            @wraps(func)
            def wrapper(self, *args, **kwargs):
                for i in range(retries):
                    try:
                        return func(self, *args, **kwargs)
                    except Exception as e:
                        if i == retries - 1:  # Last attempt
                            raise
                        wait_time = (backoff_in_seconds * 2 ** i)
                        logger.warning(f"Attempt {i + 1} failed: {str(e)}. Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
            return wrapper
        return decorator

    @retry_with_backoff()
    def get_problem_details(self, title_slug: str) -> Dict:
        """Fetch problem details from LeetCode with retry logic."""
        query = """
        query questionData($titleSlug: String!) {
            question(titleSlug: $titleSlug) {
                questionId
                title
                content
                difficulty
                topicTags {
                    name
                }
            }
        }
        """
        response = requests.post(
            self.LEETCODE_GRAPHQL_URL,
            json={'query': query, 'variables': {'titleSlug': title_slug}},
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()['data']['question']

    @retry_with_backoff()
    def get_submissions(self, limit: int = 20) -> List[Dict]:
        """Fetch recent accepted submissions with pagination."""
        url = f"{self.LEETCODE_SUBMISSIONS_URL}?offset=0&limit={limit}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        submissions = response.json().get('submissions_dump', [])
        return [s for s in submissions if s['status_display'] == 'Accepted']

    def get_file_extension(self, lang: str) -> str:
        """Get file extension for a given programming language."""
        return self.EXTENSIONS.get(lang.lower(), 'txt')

    def create_problem_readme(self, problem_data: Dict, stats: str) -> str:
        """Create README.md content for a problem."""
        return f"""# {problem_data['questionId']}. {problem_data['title']}

## Difficulty: {problem_data['difficulty']}
## Topics: {', '.join(tag['name'] for tag in problem_data['topicTags'])}

## Problem

{problem_data['content']}

## Solution Stats

| Language | Runtime | Memory | Status | Last Submission |
|----------|---------|--------|--------|-----------------|
{stats}

[View on LeetCode](https://leetcode.com/problems/{problem_data['title'].lower().replace(' ', '-')})
"""

    def process_submission(self, submission: Dict):
        """Process a single submission."""
        try:
            problem_data = self.get_problem_details(submission['title_slug'])
            
            # Create folder structure
            difficulty = problem_data['difficulty'].lower()
            folder_name = f"{int(problem_data['questionId']):04d}-{submission['title_slug']}"
            base_path = f"{difficulty}/{folder_name}"
            
            # Update solution file
            extension = self.get_file_extension(submission['lang'])
            file_path = f"{base_path}/solution.{extension}"
            
            self._update_or_create_file(
                file_path=file_path,
                content=submission['code'],
                commit_message=f"Update {submission['lang']} solution for {problem_data['title']}"
            )
            
            # Update README with submission timestamp
            submission_date = datetime.fromtimestamp(
                submission['timestamp'], 
                tz=timezone.utc
            ).strftime('%Y-%m-%d')
            
            stats = f"| {submission['lang']} | {submission['runtime']} | {submission['memory']} | ✅ | {submission_date} |\n"
            readme_content = self.create_problem_readme(problem_data, stats)
            
            self._update_or_create_file(
                file_path=f"{base_path}/README.md",
                content=readme_content,
                commit_message=f"Update README for {problem_data['title']}"
            )
            
        except Exception as e:
            logger.error(f"Error processing submission {submission['title']}: {str(e)}")
            raise

    def _update_or_create_file(self, file_path: str, content: str, commit_message: str):
        """Update or create a file in the repository."""
        try:
            # Ensure content is properly encoded
            content_bytes = content.encode('utf-8')
            
            try:
                # Try to get existing file
                contents = self.repo.get_contents(file_path)
                current_content = contents.decoded_content.decode('utf-8')
                
                # Only update if content has changed
                if current_content != content:
                    self.repo.update_file(
                        path=file_path,
                        message=commit_message,
                        content=content_bytes,
                        sha=contents.sha,
                        branch="main"
                    )
                    logger.info(f"Updated file: {file_path}")
                    
            except Exception as e:
                if "404" in str(e):  # File doesn't exist
                    # Create new file
                    self.repo.create_file(
                        path=file_path,
                        message=commit_message,
                        content=content_bytes,
                        branch="main"
                    )
                    self.path_cache.add(file_path)
                    logger.info(f"Created new file: {file_path}")
                else:
                    raise
                    
        except Exception as e:
            logger.error(f"Error handling file {file_path}: {str(e)}")
            raise

    def sync_solutions(self):
        """Main sync function."""
        logger.info("Starting LeetCode solutions sync...")
        try:
            submissions = self.get_submissions()
            for submission in submissions:
                self.process_submission(submission)
            logger.info("Sync completed successfully!")
        except Exception as e:
            logger.error(f"Sync failed: {str(e)}")
            raise
# First keep all your existing code from the LeetCodeGitHubSync class
# Then add this at the end of the file:

def main():
    """Main entry point with proper error handling and logging."""
    try:
        # Set up more detailed logging for debugging
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
        )
        
        # Get environment variables
        github_token = os.getenv('GH_PAT')
        github_repo = os.getenv('GITHUB_REPO')
        leetcode_session = os.getenv('LEETCODE_SESSION')
        
        # Validate environment variables
        if not github_token:
            raise ValueError("GH_PAT environment variable is not set")
        if not github_repo:
            raise ValueError("GITHUB_REPO environment variable is not set")
        if not leetcode_session:
            raise ValueError("LEETCODE_SESSION environment variable is not set")
            
        logger.info(f"Initializing sync for repository: {github_repo}")
        
        # Initialize and run sync
        syncer = LeetCodeGitHubSync(
            github_token=github_token,
            github_repo=github_repo,
            leetcode_session=leetcode_session
        )
        
        # Test LeetCode connection before proceeding
        logger.info("Testing LeetCode connection...")
        test_response = requests.get(
            "https://leetcode.com/api/problems/all/",
            headers=syncer.headers
        )
        test_response.raise_for_status()
        logger.info("LeetCode connection successful")
        
        # Run the sync
        syncer.sync_solutions()
        
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {str(e)}")
        raise
    except ValueError as e:
        logger.error(f"Configuration error: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise

if __name__ == "__main__":
    main()