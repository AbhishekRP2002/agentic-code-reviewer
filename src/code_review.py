import os
import sys
import requests
from github import Github, GithubException
from github.Issue import Issue
from google import genai
from google.genai import types
from jinja2 import Template
from src import issue_label_clf, logger, Fore
import argparse
import base64
from dotenv import load_dotenv
from pprint import pformat  # noqa

load_dotenv()


class Repo:
    SUMMARY_TEMPLATE_PATH = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "prompt_templates",
        "summary_prompt.jinja2",
    )
    REVIEW_TEMPLATE_PATH = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "prompt_templates",
        "code_review_prompt.jinja2",
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
        logger.info(f"Repo owner: {self.owner}")
        logger.info(f"Repo name: {self.repo}")
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
        try:
            if not all([self.owner, self.repo, self.github_token]):
                raise ValueError(
                    "Missing required environment variables: REPO_OWNER, REPO_NAME, or GITHUB_TOKEN"
                )

            github_api = Github(self.github_token)
            repository = github_api.get_repo(f"{self.owner}/{self.repo}")
            # Test access
            logger.info(f"Testing access to repository \n {repository}")

            repository.get_pulls(state="open", sort="created", direction="desc")
            return repository
        except GithubException as e:
            logger.error(f"GitHub API error: {e.status} - {e.data.get('message', '')}")
            print(
                Fore.RED
                + f"Error: Cannot access repository {self.owner}/{self.repo}. Check your token permissions."
            )
            sys.exit(1)
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            print(Fore.RED + f"Unexpected error: {str(e)}")
            sys.exit(1)

    def fetch_pull_request(self, id=None):
        try:
            if id:
                logger.info(f"Fetching pull request #{id}")
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

    def fetch_issue(self, id=None) -> Issue:
        try:
            if id:
                logger.info(f"Fetching issue #{id}")
                issue = self.repository.get_issue(id)
                if issue:
                    logger.info(f"Successfully fetched issue: {issue.title}")
                    return issue
                logger.error("Issue object is None")
                return None
            else:
                issues = self.repository.get_issues(
                    state="open", sort="created", direction="desc"
                )
                return (
                    issues[0]
                    if issues.totalCount > 0 and not issues[0].pull_request
                    else None
                )
        except GithubException as e:
            logger.error(f"GitHub API error: {e.status} - {e.data.get('message', '')}")
            logger.error(f"Response data: {e.data}")
            print(Fore.RED + f"Error fetching issue: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error while fetching issue: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Error args: {e.args}")
            print(Fore.RED + f"Error fetching issue: {str(e)}")
            return None

    def get_llm_response(self, prompt):
        google_genai_client = genai.Client(
            api_key=os.getenv("GEMINI_API_KEY"),
            http_options=types.HttpOptions(api_version="v1"),
        )
        response = google_genai_client.models.generate_content(
            model="gemini-2.0-flash-001",
            contents=prompt,
            # config=types.GenerateContentConfig(
            #     system_instruction="You are a Senior Staff Software Engineer - Machine Learning, with 10 years of experience as an IC in the AI/ML Domain.",
            #     max_output_tokens=4096,
            #     temperature=0.2,
            #     response_mime_type="application/json",
            # ),
        )
        return response.text

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
            print(Fore.YELLOW + f"Pull Request Number for summary: {pull.number}")
            print(Fore.YELLOW + f"PR Title: {pull.title}")
            if not only_diff:
                diffs, files, excluded_files = self._get_diffs_and_files(pull)
                if pull.changed_files - excluded_files > 0:
                    with open(self.SUMMARY_TEMPLATE_PATH, "r") as template_file:
                        template_content = template_file.read()
                    prompt = Template(template_content).render(
                        num_files=pull.changed_files - excluded_files,
                        diffs=diffs,
                        files=files,
                        context_flag=1,
                    )
                    completion = self.get_llm_response(prompt)
                    print(Fore.MAGENTA + completion)
                    return completion
                else:
                    print(Fore.RED + "No files to summarize.")
            else:
                print(f"{Fore.CYAN} Fetching diff URL: {pull.diff_url}")
                diff = self._fetch_file_content(pull.diff_url)
                if diff:
                    print(Fore.YELLOW + f"Diff URL: {pull.diff_url}")
                    prompt = Template(open(self.SUMMARY_TEMPLATE_PATH).read()).render(
                        diff=diff, context_flag=2
                    )
                    completion = self.get_llm_response(prompt)
                    print(Fore.MAGENTA + completion)
                    return completion
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
            # logger.info("Diffs: %s", pformat(diffs[0]))
            if pull.changed_files - excluded_files > 0:
                with open(self.REVIEW_TEMPLATE_PATH, "r") as template_file:
                    template_content = template_file.read()
                logger.info(f" {Fore.YELLOW} Template content: {template_content}")
                prompt = Template(template_content).render(
                    num_files=pull.changed_files - excluded_files,
                    diffs=diffs,
                    files=files,
                )
                # logger.info(f"Prompt to be used for PR review: {prompt}")
                completion = self.get_llm_response(prompt)
                print(Fore.MAGENTA + completion)
                return completion
            else:
                print(Fore.RED + "No files to review.")
            prompt = Template(open(self.REVIEW_TEMPLATE_PATH).read()).render(
                num_files=pull.changed_files - excluded_files, diffs=diffs, files=files
            )
            completion = self.get_llm_response(prompt)
            print(Fore.MAGENTA + completion)
            return completion
        else:
            print(Fore.RED + "Can't load pull request.")

    def label_issue(self):
        try:
            issue = self.fetch_issue(self.event_number)
            if isinstance(issue, Issue) and issue:
                return issue_label_clf.label_issue(issue.title, issue.body)
        except Exception as e:
            logger.error(
                f"Error in labeling issue: {e.status} - {e.data.get('message', '')}"
            )
            print(Fore.RED + "Can't find issue.")

    def create_label(self, label=None):
        self.repository.get_issue(self.event_number).set_labels(label)
        print(Fore.GREEN + "Label created successfully!")

    def create_comment(self, comment=None):
        self.repository.get_issue(self.event_number).create_comment(comment)
        print(Fore.GREEN + "Comment created successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Code Review Agent GitHub event handler"
    )
    parser.add_argument(
        "event_type",
        choices=["label_issue", "review_pr", "summarize_pr"],
        default="label_issue",
        help="Type of GitHub event",
    )
    args = parser.parse_args()

    repo = Repo()

    if args.event_type == "label_issue":
        label = repo.label_issue()
        if label:
            repo.create_label(label)
    elif args.event_type == "review_pr":
        review_comment = repo.review_pull_request()
        if review_comment:
            repo.create_comment(review_comment)
    elif args.event_type == "summarize_pr":
        summary_comment = repo.summarize_pull_request(only_diff=True)
        if summary_comment:
            repo.create_comment(summary_comment)
