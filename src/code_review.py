import os
import requests
from github import Github
from colorama import init, Fore
from langchain_openai import AzureOpenAI
from jinja2 import Template
from src import issue_label_clf
import argparse
import base64

# Initialize Colorama for colorful console output
init(autoreset=True)


class Repo:
    SUMMARY_TEMPLATE_PATH = os.path.join(
        os.path.dirname(__file__), "prompt_templates", "code_review_prompt.jinja2"
    )
    REVIEW_TEMPLATE_PATH = os.path.join(
        os.path.dirname(__file__), "prompt_templates", "summary_prompt.jinja2"
    )
    DEFAULT_EXCLUDES = [
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".ico",
        ".json",
        ".ipynb",
        ".pdf",
        ".csv",
    ]

    def __init__(self):
        self.owner = os.getenv("REPO_OWNER")
        self.repo = os.getenv("REPO_NAME")
        self.event_number = int(os.getenv("EVENT_NUMBER"))
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.azure_openai_api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.azure_openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.repository = self.get_repo()
        exclude_extensions = os.getenv("EXCLUDE_EXTENSIONS")
        if exclude_extensions:
            self.exclude_extensions = list(
                set(
                    [ext.strip() for ext in exclude_extensions.split(",")]
                    + self.DEFAULT_EXCLUDES
                )
            )
        else:
            self.exclude_extensions = self.DEFAULT_EXCLUDES.copy()

    def get_repo(self):
        github_api = Github(self.github_token)
        repository = github_api.get_repo(f"{self.owner}/{self.repo}")
        return repository

    def fetch_pull_request(self, id=None):
        try:
            if id:
                return (
                    self.repository.get_pull(id)
                    if self.repository.get_pull(id)
                    else None
                )
            else:
                pulls = self.repository.get_pulls(
                    state="open", sort="created", direction="desc"
                )
                return pulls[0] if pulls.totalCount > 0 else None
        except Exception as e:
            print(Fore.RED + f"Error fetching pull request: {str(e)}")
            return None

    def fetch_issue(self, id=None):
        try:
            if id:
                return (
                    self.repository.get_issue(id)
                    if self.repository.get_issue(id)
                    else None
                )
            else:
                issues = self.repository.get_issues(
                    state="open", sort="created", direction="desc"
                )
                return (
                    issues[0]
                    if issues.totalCount > 0 and not issues[0].pull_request
                    else None
                )
        except Exception as e:
            print(Fore.RED + f"Error fetching issue: {str(e)}")
            return None

    def setup_llm_completion(self, prompt):
        client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_deployment="gpt-4o",
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_version="2024-08-01-preview",
            temperature=0.5,
            max_retries=3,
        )
        return client.ainvoke(prompt)

    def _fetch_file_content(self, contents_url):
        response = requests.get(
            contents_url, headers={"Authorization": f"Bearer {self.github_token}"}
        )
        if response.status_code == 200:
            decoded_content = base64.b64decode(response.json()["content"]).decode(
                "utf-8"
            )
            return decoded_content
        else:
            print(
                Fore.YELLOW
                + f"Failed to fetch file content. Status code: {response.status_code}"
            )
            return ""

    def _get_diffs_and_files(self, pull):
        diffs = []
        files = []
        excluded_files = 0
        for i in range(pull.changed_files):
            filename = pull.get_files()[i].filename
            if not any(filename.endswith(ext) for ext in self.exclude_extensions):
                patch = pull.get_files()[i].patch
                contents_url = pull.get_files()[i].contents_url
                file_content = self._fetch_file_content(contents_url)
                diffs.append(patch)
                files.append(file_content)
            else:
                excluded_files += 1
                print(f"{filename} excluded based on extension")
        return diffs, files, excluded_files

    def summarize_pull_request(self, only_diff=False):
        pull = self.fetch_pull_request(self.event_number)
        if pull:
            print(Fore.YELLOW + f"Pull Request Number: {pull.number}")
            print(Fore.YELLOW + f"Title: {pull.title}")
            if not only_diff:
                diffs, files, excluded_files = self._get_diffs_and_files(pull)
                if pull.changed_files - excluded_files > 0:
                    prompt = Template(open(self.SUMMARY_TEMPLATE_PATH).read()).render(
                        num_files=pull.changed_files - excluded_files,
                        diffs=diffs,
                        files=files,
                        context_flag=1,
                    )
                    completion = self.setup_groq_completion(prompt)
                    print(Fore.MAGENTA + completion.choices[0].message.content)
                    return completion.choices[0].message.content
                else:
                    print(Fore.RED + "No files to summarize.")
            else:
                diff = self._fetch_file_content(pull.diff_url)
                if diff:
                    print(Fore.YELLOW + f"Diff URL: {pull.diff_url}")
                    prompt = Template(open(self.SUMMARY_TEMPLATE_PATH).read()).render(
                        diff=diff, context_flag=2
                    )
                    completion = self.setup_groq_completion(prompt)
                    print(Fore.MAGENTA + completion.choices[0].message.content)
                    return completion.choices[0].message.content
                else:
                    print(Fore.RED + "Failed to fetch diff data.")
        else:
            print(Fore.RED + "Can't load pull request.")

    def review_pull_request(self):
        pull = self.fetch_pull_request(self.event_number)
        if pull:
            print(Fore.YELLOW + f"Pull Request Number: {pull.number}")
            print(Fore.YELLOW + f"Title: {pull.title}")
            diffs, files, excluded_files = self._get_diffs_and_files(pull)
            if pull.changed_files - excluded_files > 0:
                prompt = Template(open(self.REVIEW_TEMPLATE_PATH).read()).render(
                    num_files=pull.changed_files - excluded_files,
                    diffs=diffs,
                    files=files,
                )
                completion = self.setup_groq_completion(prompt)
                print(Fore.MAGENTA + completion.choices[0].message.content)
                return completion.choices[0].message.content
            else:
                print(Fore.RED + "No files to review.")
            prompt = Template(open(self.REVIEW_TEMPLATE_PATH).read()).render(
                num_files=pull.changed_files - excluded_files, diffs=diffs, files=files
            )
            completion = self.setup_groq_completion(prompt)
            print(Fore.MAGENTA + completion.choices[0].message.content)
            return completion.choices[0].message.content
        else:
            print(Fore.RED + "Can't load pull request.")

    def label_issue(self):
        issue = self.fetch_issue(self.event_number)
        if issue:
            return issue_label_clf.label_issue(issue.title, issue.body)
        else:
            print(Fore.RED + "Can't find issue.")

    def create_label(self, label=None):
        self.repository.get_issue(self.event_number).set_labels(label)
        print(Fore.GREEN + "Label created successfully.")

    def create_comment(self, comment=None):
        self.repository.get_issue(self.event_number).create_comment(comment)
        print(Fore.GREEN + "Comment created successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RepoFix GitHub event handler")
    parser.add_argument(
        "event_type", choices=["issues", "pull_request"], help="Type of GitHub event"
    )
    args = parser.parse_args()

    repo = Repo()

    if args.event_type == "issues":
        label = repo.label_issue()
        if label:
            repo.create_label(label)
    elif args.event_type == "pull_request":
        review_comment = repo.review_pull_request()
        if review_comment:
            repo.create_comment(review_comment)
