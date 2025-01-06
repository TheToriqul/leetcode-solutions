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
    EXTENSIONS = {
        'python': 'py', 'python3': 'py', 'java': 'java',
        'c': 'c', 'c++': 'cpp', 'javascript': 'js',
        'typescript': 'ts', 'golang': 'go', 'ruby': 'rb',
        'swift': 'swift', 'kotlin': 'kt', 'rust': 'rs',
        'scala': 'scala', 'php': 'php'
    }

    LEETCODE_GRAPHQL_URL = "https://leetcode.com/graphql"
    LEETCODE_SUBMISSIONS_URL = "https://leetcode.com/api/submissions/"
    CACHE_FILE = "solutions_cache.json"

    def __init__(self, github_token: str, github_repo: str, leetcode_session: str):
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
            except:
                self.repo.create_file(
                    self.CACHE_FILE,
                    "chore: Create solutions cache",
                    cache_content
                )
        except Exception as e:
            logger.error(f"Error saving cache: {str(e)}")

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

    def get_submissions(self, limit: int = 20) -> List[Dict]:
        """Fetch recent accepted submissions."""
        url = f"{self.LEETCODE_SUBMISSIONS_URL}?offset=0&limit={limit}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return [s for s in submissions if s['status_display'] == 'Accepted']

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

            # Get problem details only for new solutions
            if cache_key not in self.solutions_cache:
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
                self.repo.update_file(
                    file_path,
                    f"feat: Update {lang} solution for {problem_data['title']}",
                    submission['code'],
                    contents.sha
                )
            except:
                self.repo.create_file(
                    file_path,
                    f"feat: Add {lang} solution for {problem_data['title']}",
                    submission['code']
                )

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
        github_token = os.getenv('GH_PAT')
        github_repo = os.getenv('GITHUB_REPO')
        leetcode_session = os.getenv('LEETCODE_SESSION')
        
        if not all([github_token, github_repo, leetcode_session]):
            raise ValueError("Missing required environment variables")
            
        logger.info(f"Initializing sync for repository: {github_repo}")
        
        syncer = LeetCodeGitHubSync(
            github_token=github_token,
            github_repo=github_repo,
            leetcode_session=leetcode_session
        )
        
        logger.info("Testing LeetCode connection...")
        test_response = requests.get(
            "https://leetcode.com/api/problems/all/",
            headers=syncer.headers
        )
        test_response.raise_for_status()
        logger.info("LeetCode connection successful")
        
        syncer.sync_solutions()
        
    except Exception as e:
        logger.error(f"Sync failed: {str(e)}")
        raise

if __name__ == "__main__":
    main()