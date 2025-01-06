import os
import requests
from github import Github
from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional
import time
from functools import wraps
import hashlib
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LeetCodeGitHubSync:
    """Class to handle synchronization of LeetCode solutions to GitHub."""
    
    # Language to file extension mapping
    EXTENSIONS = {
        'python': 'py', 'python3': 'py', 'java': 'java',
        'c': 'c', 'c++': 'cpp', 'javascript': 'js',
        'typescript': 'ts', 'golang': 'go', 'ruby': 'rb',
        'swift': 'swift', 'kotlin': 'kt', 'rust': 'rs',
        'scala': 'scala', 'php': 'php'
    }

    # API endpoints
    LEETCODE_GRAPHQL_URL = "https://leetcode.com/graphql"
    LEETCODE_SUBMISSIONS_URL = "https://leetcode.com/api/submissions/"

    def __init__(self, github_token: str, github_repo: str, leetcode_session: str):
        """Initialize with required credentials."""
        if not all([github_token, github_repo, leetcode_session]):
            raise ValueError("Missing required credentials")

        self.github = Github(github_token)
        self.repo = self.github.get_repo(github_repo)
        self.headers = {
            'Cookie': f'LEETCODE_SESSION={leetcode_session}',
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://leetcode.com'
        }
        # Cache for existing files and their content hashes
        self.path_cache = {}
        self._init_path_cache()

    def _init_path_cache(self):
        """Initialize cache of existing paths and their content hashes."""
        try:
            contents = self.repo.get_contents("")
            while contents:
                file_content = contents.pop(0)
                if file_content.type == "file":
                    self.path_cache[file_content.path] = hashlib.sha256(
                        file_content.decoded_content
                    ).hexdigest()
                if file_content.type == "dir":
                    contents.extend(self.repo.get_contents(file_content.path))
        except Exception as e:
            logger.error(f"Error initializing path cache: {str(e)}")
            raise

    def _calculate_content_hash(self, content: str) -> str:
        """Calculate hash of content for comparison."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

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
        """Fetch problem details from LeetCode."""
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
        """Fetch recent accepted submissions."""
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

    def _update_or_create_file(self, file_path: str, content: str, commit_message: str):
        """Update or create a file in the repository only if content has changed."""
        try:
            # Calculate hash of new content
            new_content_hash = self._calculate_content_hash(content)
            
            # Check if file exists and content has changed
            if file_path in self.path_cache:
                if self.path_cache[file_path] == new_content_hash:
                    logger.debug(f"Content unchanged for {file_path}, skipping update")
                    return
                
                # Content has changed, update the file
                contents = self.repo.get_contents(file_path)
                self.repo.update_file(
                    path=file_path,
                    message=commit_message,
                    content=content.encode('utf-8'),
                    sha=contents.sha,
                    branch="main"
                )
                logger.info(f"Updated file: {file_path}")
            else:
                # Create new file
                self.repo.create_file(
                    path=file_path,
                    message=commit_message,
                    content=content.encode('utf-8'),
                    branch="main"
                )
                logger.info(f"Created new file: {file_path}")
            
            # Update cache with new content hash
            self.path_cache[file_path] = new_content_hash
                    
        except Exception as e:
            logger.error(f"Error handling file {file_path}: {str(e)}")
            raise

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

def main():
    """Main entry point with proper error handling and logging."""
    try:
        # Get environment variables
        github_token = os.getenv('GH_PAT')
        github_repo = os.getenv('GITHUB_REPO')
        leetcode_session = os.getenv('LEETCODE_SESSION')
        
        # Validate environment variables
        if not all([github_token, github_repo, leetcode_session]):
            raise ValueError("Missing required environment variables")
            
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