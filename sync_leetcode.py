import os
import requests
from github import Github
from datetime import datetime
import json

class LeetCodeGitHubSync:
    def __init__(self, github_token, github_repo, leetcode_session):
        self.github = Github(github_token)
        self.repo = self.github.get_repo(github_repo)
        self.headers = {
            'Cookie': f'LEETCODE_SESSION={leetcode_session}',
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://leetcode.com'
        }
        
    def get_problem_details(self, title_slug):
        """Fetch problem details from LeetCode"""
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
        url = "https://leetcode.com/graphql"
        response = requests.post(
            url,
            json={'query': query, 'variables': {'titleSlug': title_slug}},
            headers=self.headers
        )
        return response.json()['data']['question']

    def get_submissions(self):
        """Fetch recent submissions"""
        url = "https://leetcode.com/api/submissions/?offset=0&limit=20"
        response = requests.get(url, headers=self.headers)
        return response.json().get('submissions_dump', [])

    def create_problem_readme(self, problem_data, stats):
        """Create README.md for problem"""
        return f"""# {problem_data['questionId']}. {problem_data['title']}

## Difficulty: {problem_data['difficulty']}
## Topics: {', '.join(tag['name'] for tag in problem_data['topicTags'])}

## Problem

{problem_data['content']}

## Solution Stats

| Language | Runtime | Memory | Status | Date |
|----------|---------|--------|--------|------|
{stats}

[View on LeetCode](https://leetcode.com/problems/{problem_data['title'].lower().replace(' ', '-')})
"""

    def get_file_extension(self, lang):
        """Get file extension for programming language"""
        extensions = {
            'python': 'py',
            'python3': 'py',
            'java': 'java',
            'cpp': 'cpp',
            'c++': 'cpp',
            'javascript': 'js',
            'typescript': 'ts',
            'golang': 'go',
            'ruby': 'rb',
            'swift': 'swift',
            'kotlin': 'kt',
            'rust': 'rs',
            'scala': 'scala',
            'php': 'php'
        }
        return extensions.get(lang.lower(), 'txt')

    def create_solution_file(self, submission, problem_data):
        """Create solution file content"""
        return f"""# {problem_data['questionId']}. {problem_data['title']}
# Difficulty: {problem_data['difficulty']}
# Runtime: {submission['runtime']}
# Memory: {submission['memory']}

{submission['code']}
"""

    def sync_solutions(self):
        """Main sync function"""
        print("Starting LeetCode solutions sync...")
        submissions = self.get_submissions()
        
        for submission in submissions:
            if submission['status_display'] != 'Accepted':
                continue
                
            try:
                print(f"\nProcessing submission for: {submission['title']}")
                
                problem_data = self.get_problem_details(submission['title_slug'])
                
                # Create folder structure
                difficulty = problem_data['difficulty'].lower()
                folder_name = f"{int(problem_data['questionId']):04d}-{submission['title_slug']}"
                base_path = f"{difficulty}/{folder_name}"
                
                # Get file extension
                extension = self.get_file_extension(submission['lang'])
                file_name = f"solution.{extension}"
                file_path = f"{base_path}/{file_name}"
                
                # Create solution file
                solution_content = self.create_solution_file(submission, problem_data)
                
                # Check if file exists and get its SHA
                try:
                    contents = self.repo.get_contents(file_path)
                    # File exists, update it
                    self.repo.update_file(
                        path=file_path,
                        message=f"Update {submission['lang']} solution for {problem_data['title']}",
                        content=solution_content,
                        sha=contents.sha
                    )
                    print(f"Updated existing solution file: {file_path}")
                except Exception as e:
                    if "Not Found" in str(e):
                        # File doesn't exist, create it
                        try:
                            # Ensure directory exists by trying to create README first
                            readme_path = f"{base_path}/README.md"
                            try:
                                self.repo.get_contents(readme_path)
                            except:
                                self.repo.create_file(
                                    path=readme_path,
                                    message=f"Initialize directory for {problem_data['title']}",
                                    content="# Initializing..."
                                )
                            
                            # Now create the solution file
                            self.repo.create_file(
                                path=file_path,
                                message=f"Add {submission['lang']} solution for {problem_data['title']}",
                                content=solution_content
                            )
                            print(f"Created new solution file: {file_path}")
                        except Exception as create_error:
                            print(f"Error creating solution file: {str(create_error)}")
                            continue
                    else:
                        print(f"Error handling solution file: {str(e)}")
                        continue

                # Update README
                try:
                    solutions_stats = ""
                    try:
                        dir_contents = self.repo.get_contents(base_path)
                        for content in dir_contents:
                            if content.name.startswith('solution.'):
                                lang = content.name.split('.')[1].upper()
                                solutions_stats += f"| {lang} | {submission['runtime']} | {submission['memory']} | ✅ | {datetime.now().strftime('%Y-%m-%d')} |\n"
                    except:
                        solutions_stats = f"| {submission['lang']} | {submission['runtime']} | {submission['memory']} | ✅ | {datetime.now().strftime('%Y-%m-%d')} |\n"

                    readme_content = self.create_problem_readme(problem_data, solutions_stats)
                    
                    try:
                        readme = self.repo.get_contents(f"{base_path}/README.md")
                        self.repo.update_file(
                            path=f"{base_path}/README.md",
                            message=f"Update README for {problem_data['title']}",
                            content=readme_content,
                            sha=readme.sha
                        )
                        print(f"Updated README for: {problem_data['title']}")
                    except Exception as readme_error:
                        if "Not Found" in str(readme_error):
                            self.repo.create_file(
                                path=f"{base_path}/README.md",
                                message=f"Add README for {problem_data['title']}",
                                content=readme_content
                            )
                            print(f"Created README for: {problem_data['title']}")
                        else:
                            raise readme_error
                except Exception as e:
                    print(f"Error handling README: {str(e)}")

            except Exception as e:
                print(f"Error processing submission {submission['title']}: {str(e)}")
                continue

        print("\nSync completed!")

if __name__ == "__main__":
    github_token = os.getenv("GH_PAT")
    github_repo = os.getenv("GITHUB_REPO")
    leetcode_session = os.getenv("LEETCODE_SESSION")
    
    syncer = LeetCodeGitHubSync(github_token, github_repo, leetcode_session)
    syncer.sync_solutions()