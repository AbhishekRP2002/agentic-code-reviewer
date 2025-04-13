# annotated notes for the project

features to include:
- identify the issue type or label the issue
- provide PR summary
- perform code review checking for code smells, adherence to style guides (like PEP 8, Google Style Guides), complexity metrics (cyclomatic complexity), and anti-patterns.
- suggest code changes
- static analysis like linting and type checking
- automatically generate PR descriptions and changelogs
- maybe think around suggesting unit level tests based on the changes in the PR ?

how do i build a context aware system which keeps track of the PR history of the project and other events ?
- maybe use a db as knowledge base layer to store PR data and other events
