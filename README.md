# Agentic Code Reviewer

 - LLM-powered code reviews and issue labelling directly in your GitHub workflow.
 - This action uses Google's Gemini API to analyze code changes and automatically provide review comments or suggest labels for issues.

## Features

* **AI-Powered Code Review:** Analyzes code diffs in Pull Requests to identify potential issues, suggest improvements, and check for best practices.
* **Automated PR Summarization:** Provides concise summaries of changes in a Pull Request.
* **Intelligent Issue Labelling:** Automatically classifies new issues (e.g., "bug", "enhancement", "question") using a pre-trained model.
* **Configurable:** Exclude specific file extensions from review.
* **GitHub Action:** Integrates seamlessly into your CI/CD pipeline.

## Setup

1.  **Get Gemini API Key:** Obtain an API key for the Gemini API from Google AI Studio or Google Cloud.
2.  **Add Secret to GitHub Repository:** Add the obtained API key as an Actions secret in the repository where you intend to use this action.
    * Go to your repository `Settings` > `Secrets and variables` > `Actions`.
    * Click `New repository secret`.
    * Name the secret `GEMINI_API_KEY`.
    * Paste your API key into the value field.

## Usage (GitHub Action)

Create a workflow file in your repository (e.g., `.github/workflows/code_review.yml`) to use this action.

```yaml
name: Code Reviewer

on:
  pull_request:
    types: [opened, synchronize, reopened]
  issues:
    types: [opened]

jobs:
  agentic-review:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
      issues: write

    steps:
        # Step 1: Checkout the repository
      - name: Checkout repository
        uses: actions/checkout@v4
        # Optional: Fetch full history if needed for more context (can increase time)
        # with:
        #  fetch-depth: 0

      # Step 2: Run the Agentic Code Reviewer Action
      - name: Run Code Reviewer Agent
        # Replace {owner}/{repo} with your action's repo, or use './' for self-testing
        # Replace {ref} with a specific commit SHA, tag, or branch (e.g., v1.0.0 or main)
        uses: {owner}/{repo}@{ref} # Example: uses: your-username/agentic-code-reviewer@main
        with:
          gemini_api_key: ${{ secrets.GEMINI_API_KEY }}

          # Optional: Exclude specific file extensions (comma-separated)
          # exclude_extensions: '.md,.txt,.log'

          # The github_token is provided automatically by the runner
          # github_token: ${{ secrets.GITHUB_TOKEN }} # added automatically by the runner
```

[Use this action with your project](https://github.com/marketplace/actions/code-reviewer-agent)
