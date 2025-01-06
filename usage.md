# LeetCode Solutions Sync - Usage Guide

## Overview
This tool automatically syncs your LeetCode solutions to GitHub, organizing them by difficulty level and maintaining detailed documentation for each problem.

## Prerequisites
- GitHub account
- LeetCode account
- Python 3.10 or higher

## Setup Steps

### 1. Repository Setup
1. Fork or clone this repository
2. Go to your repository's Settings > Secrets and variables > Actions
3. Add the following secrets:
   - `GH_PAT`: Your GitHub Personal Access Token (with repo access)
   - `LEETCODE_SESSION`: Your LeetCode session cookie

### 2. Getting Required Secrets

#### GitHub Personal Access Token (GH_PAT)
1. Go to GitHub Settings > Developer settings > Personal access tokens > Tokens (classic)
2. Click "Generate new token (classic)"
3. Select the following scopes:
   - `repo` (Full control of private repositories)
4. Copy the generated token and save it as `GH_PAT` in your repository secrets

#### LeetCode Session Cookie (LEETCODE_SESSION)
1. Login to LeetCode in your browser
2. Open Developer Tools (F12)
3. Go to Application > Cookies > leetcode.com
4. Find and copy the value of `LEETCODE_SESSION`
5. Save it as `LEETCODE_SESSION` in your repository secrets

## How It Works

### Automatic Sync
- The sync runs automatically at midnight on the 1st of every month
- Solutions are organized in folders by difficulty:
  ```
  easy/
  medium/
  hard/
  ```

### Manual Sync
You can trigger a manual sync:
1. Go to your repository's Actions tab
2. Select "Sync LeetCode Solutions" workflow
3. Click "Run workflow"

### Solution Structure
Each problem gets its own folder with:
```
difficulty/
└── xxxx-problem-name/
    ├── README.md       # Problem details & stats
    └── solution.{ext}  # Your solution file
```

### File Types Support
- Python (.py)
- JavaScript (.js)
- Java (.java)
- C++ (.cpp)
- And other LeetCode-supported languages

## Workflow Details
- Syncs only accepted solutions
- Updates existing solutions if improved
- Maintains problem descriptions and statistics
- Organizes by difficulty level
- Supports multiple programming languages

## Troubleshooting

### Common Issues

1. **Workflow Failed**
   - Check if your secrets are correctly set
   - Verify your LeetCode session is still valid
   - Check GitHub Actions logs for specific errors

2. **Solutions Not Syncing**
   - Ensure solutions are "Accepted" on LeetCode
   - Check if LeetCode session is expired
   - Verify repository permissions

3. **Missing Problems**
   - Only accepted solutions are synced
   - Check last sync date in Actions tab
   - Try running manual sync

### Getting Help
If you encounter issues:
1. Check the Actions tab for error logs
2. Verify your secrets are correctly set
3. Ensure your LeetCode session is valid

## Best Practices
1. Solve problems on LeetCode first
2. Ensure solutions are accepted before sync
3. Use clear, well-documented code
4. Commit any manual changes before sync

## Notes
- The sync only picks up "Accepted" solutions
- Each problem's README includes:
  - Problem description
  - Difficulty level
  - Your solution's stats
  - Submission date
  - LeetCode problem link