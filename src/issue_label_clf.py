import os
from typing import Literal
from openai import AzureOpenAI
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from src import logger, Fore  # noqa
from pprint import pformat

load_dotenv()


def preprocess(issue_title, issue_body):
    doc = f"{str(issue_title)} {str(issue_body)}"
    doc = " ".join(doc.split())
    return doc


class IssueLabel(BaseModel):
    label: Literal[
        "bug",
        "enhancement",
        "question",
        "documentation",
        "help wanted",
        "good first issue",
    ] = Field(
        ...,
        description="The label for the issue: bug, enhancement, question, documentation, help wanted, or good first issue.",
    )
    confidence: float = Field(
        ...,
        description="The confidence score of the label prediction by the language model.",
    )
    reasoning: str = Field(
        ...,
        description="The reasoning behind the label prediction by the language model.",
    )


def label_issue(issue_title, issue_body):
    # issue_data = preprocess(issue_title, issue_body)
    # Load the original configuration
    client = AzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_version="2025-01-01-preview",
    )
    prompt = f"""Analyze this GitHub issue and classify it as either 'bug', 'enhancement', 'question', 'documentation', 'help wanted', or 'good first issue'.
    
    Issue Title: {issue_title}
    Issue Description: {issue_body}
    
    Provide your response strictly in JSON format with the following keys:
    - label: The classification (bug/enhancement/question)
    - confidence: A number between 0 and 1
    - reasoning: Brief explanation for the classification
    """
    response = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        response_format=IssueLabel,
        messages=[
            {
                "role": "system",
                "content": "You are an expert GitHub issue classifier that provides structured JSON outputs.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        max_tokens=4096,
    )

    result = response.choices[0].message.parsed
    logger.info(f"{Fore.GREEN} Issue classification result: {pformat(result)}")
    return result.label
