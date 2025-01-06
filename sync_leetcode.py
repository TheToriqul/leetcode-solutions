import os
import json
import requests
from github import Github
from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional
import time
from functools import wraps
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
    CACHE_FILE = "solutions_cache.json"

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
        self.solutions_cache = self.load_cache()

    def load_cache(self) -> Dict:
        """Load the solutions cache from the repository."""
        try:
            contents = self.repo.get_contents(self.CACHE_FILE)
            cache_content = contents.decoded_content.decode('utf-8')
            return json.loads(cache_content)
        except:
            logger.info("No cache file found, creating new cache")
            return {}

    def save_cache(self):
        """Save the solutions cache to the repository."""
        try:
            cache_content = json.dumps(self.solutions_cache, indent=2)
            try:
                contents = self.repo.get_contents(self.CACHE_FILE)
                self.repo.update_file(
                    self.CACHE_FILE,
                    "chore: Update solutions cache",
                    cache_content,
                    contents.sha
                )
                logger.info("Cache file updated")
            except:
                self.repo.create_file(
                    self.CACHE_FILE,
                    "chore: Create solutions cache",
                    cache_content
                )
                logger.info("Cache file created")
        except Exception as e:
            logger.error(f"Error saving cache: {str(e)}")

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
        try:
            response = requests.post(
                self.LEETCODE_GRAPHQL_URL,
                json={'query': query, 'variables': {'titleSlug': title_slug}},
                headers=self.headers
            )
            response.raise_for_status()
            data = response.json()
            return data['data']['question']
        except Exception as e:
            logger.error(f"Error fetching problem details for {title_slug}: {str(e)}")
            raise

    @retry_with_backoff()
    def get_submissions(self, limit: int = 20) -> List[Dict]:
        """Fetch recent accepted submissions."""
        try:
            url = f"{self.LEETCODE_SUBMISSIONS_URL}?offset=0&limit={limit}"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            # Get submissions from response
            submissions_data = response.json()
            submissions = submissions_data.get('submissions_dump', [])
            
            # Filter for accepted submissions
            accepted_submissions = [s for s in submissions if s['status_display'] == 'Accepted']
            
            logger.info(f"Found {len(accepted_submissions)} accepted submissions")
            return accepted_submissions
        except Exception as e:
            logger.error(f"Error fetching submissions: {str(e)}")
            raise

    def get_file_extension(self, lang: str) -> str:
        """Get file extension for a given programming language."""
        return self.EXTENSIONS.get(lang.lower(), 'txt')

    def create_problem_readme(self, problem_data: Dict) -> str:
        """Create README.md content for a new problem."""
        return f"""# {problem_data['questionId']}. {problem_data['title']}

## Difficulty: {problem_data['difficulty']}
## Topics: {', '.join(tag['name'] for tag in problem_data['topicTags'])}

## Problem

{problem_data['content']}

[View on LeetCode](https://leetcode.com/problems/{problem_data['title'].lower().replace(' ', '-')})
"""

    def process_submission(self, submission: Dict):
        """Process a single submission."""
        try:
            # Create cache key
            problem_id = submission['title_slug']
            lang = submission['lang'].lower()
            cache_key = f"{problem_id}_{lang}"

            # Check if solution exists and has changed
            if cache_key in self.solutions_cache:
                if self.solutions_cache[cache_key] == submission['code']:
                    logger.debug(f"Solution unchanged for {problem_id} in {lang}")
                    return

            # Get problem details
            problem_data = self.get_problem_details(submission['title_slug'])
            
            # Create folder structure
            difficulty = problem_data['difficulty'].lower()
            folder_name = f"{int(problem_data['questionId']):04d}-{submission['title_slug']}"
            base_path = f"{difficulty}/{folder_name}"

            # Create README only for new problems
            readme_path = f"{base_path}/README.md"
            try:
                self.repo.get_contents(readme_path)
            except:
                logger.info(f"Creating README for {problem_id}")
                readme_content = self.create_problem_readme(problem_data)
                self.repo.create_file(
                    readme_path,
                    f"docs: Add README for {problem_data['title']}",
                    readme_content
                )

            # Update solution file
            extension = self.get_file_extension(lang)
            file_path = f"{base_path}/solution.{extension}"
            
            try:
                contents = self.repo.get_contents(file_path)
                if contents.decoded_content.decode('utf-8') != submission['code']:
                    self.repo.update_file(
                        file_path,
                        f"feat: Update {lang} solution for {problem_data['title']}",
                        submission['code'],
                        contents.sha
                    )
                    logger.info(f"Updated solution for {problem_id} in {lang}")
            except:
                self.repo.create_file(
                    file_path,
                    f"feat: Add {lang} solution for {problem_data['title']}",
                    submission['code']
                )
                logger.info(f"Created new solution for {problem_id} in {lang}")

            # Update cache
            self.solutions_cache[cache_key] = submission['code']
            
        except Exception as e:
            logger.error(f"Error processing submission {submission['title_slug']}: {str(e)}")
            raise

    def sync_solutions(self):
        """Main sync function."""
        logger.info("Starting LeetCode solutions sync...")
        try:
            submissions = self.get_submissions()
            for submission in submissions:
                self.process_submission(submission)
            
            # Save cache after processing all submissions
            self.save_cache()
            logger.info("Sync completed successfully!")
        except Exception as e:
            logger.error(f"Sync failed: {str(e)}")
            raise

def main():
    """Main entry point."""
    try:
        # Get environment variables
        github_token = os.getenv('GH_PAT')
        github_repo = os.getenv('GITHUB_REPO')
        leetcode_session = os.getenv('LEETCODE_SESSION')
        
        # Validate environment variables
        if not all([github_token, github_repo, leetcode_session]):
            raise ValueError("Missing required environment variables")
            
        logger.info(f"Initializing sync for repository: {github_repo}")
        
        # Initialize syncer
        syncer = LeetCodeGitHubSync(
            github_token=github_token,
            github_repo=github_repo,
            leetcode_session=leetcode_session
        )
        
        # Test LeetCode connection
        logger.info("Testing LeetCode connection...")
        test_response = requests.get(
            "https://leetcode.com/api/problems/all/",
            headers=syncer.headers
        )
        test_response.raise_for_status()
        logger.info("LeetCode connection successful")
        
        # Run sync
        syncer.sync_solutions()
        
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {str(e)}")
        raise
    except ValueError as e:
        logger.error(f"Configuration error: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Sync failed: {str(e)}")
        raise

if __name__ == "__main__":
    main()