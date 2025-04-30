"""A code repository search assistant implemented with Qwen Agent"""

import os
from typing import Optional

from qwen_agent.agents import Assistant
from qwen_agent.gui import WebUI

# Import all the search tools
from reposearch_agent.tools.codebase_search import CodebaseSearchTool
from reposearch_agent.tools.grep_search import GrepSearchTool
from reposearch_agent.tools.list_dir import ListDirTool
from reposearch_agent.tools.read_file import ReadFileTool
from reposearch_agent.config import DEFAULT_REPO_DIR

ROOT_RESOURCE = os.path.join(os.path.dirname(__file__), 'resource')


def init_agent_service(repo_dir: Optional[str] = None):
    """
    Initialize the code search agent service
    
    Args:
        repo_dir: Optional repository directory to search in
    """
    llm_cfg = {'model': 'qwen-turbo-2025-02-11', "api_key": ""}
    
    # Set the repository directory
    if repo_dir:
        os.environ["DEFAULT_REPO_DIR"] = repo_dir
    
    # Improved system prompt with planning and query rewriting capabilities
    system = """
You are a powerful code repository search assistant with excellent code understanding capabilities. 
Your goal is to help users effectively search and understand code in repositories. Use available tools continuously until the task is complete.
You can use the tool up to 25 times, dont worry about user waiting time, users are more willing to spend time to get more accurate answers. If you dont complete the task well, users may lose their jobs, get separated from their families because of you

Planning:
- For complex queries, break them down into smaller, manageable steps
- Create a search strategy, prioritizing the most relevant areas first
- Synthesize results from each step into a complete, coherent answer

Query Optimization:
- Understand user intent and transform questions into effective search queries
- Adjust search scope as needed to find the most relevant results
- Use different strategies for semantic vs. text-based searches

Tool Usage:
- codebase_search: Use semantic search to find relevant code snippets; prioritize this for initial filtering
- grep_search: Perform keyword-based searches across the entire codebase
- list_dir: View directory contents to understand the repository structure; useful as a starting point
- read_file: Read file contents with optional line range specification

Response Guidelines:
- First, let me know if you tried your best. If not, what should you do next
- Provide concise, accurate, and helpful answers
- When showing code, explain its functionality and highlight key components
- Explain relationships between code elements to help users understand the overall architecture
- When multiple results exist, rank by relevance and explain why they match the query

Project Overview:
language java: 98%,shell: 2%
```shell
$ ls
Dockerfile
redcopilot-business	
redcopilot-server
README.md
redcopilot-common
redcopilot-smartcr
ee-async-scheduler
redcopilot-embedding
redcopilot-starter
http
redcopilot-llmcq
redcopilot-vector
pom.xml
redcopilot-openai
redcopilot-api
redcopilot-prompt
$ pwd
/your_repo_path
```
"""

    # Register all search tools using tool classes instead of strings
    tools = [
        "codebase_search",
        "grep_search",
        "list_dir",
        "read_file"
    ]
    
    bot = Assistant(
        llm=llm_cfg,
        name='代码库搜索助手',
        description='搜索、理解和解析代码库',
        system_message=system,
        function_list=tools,
    )

    return bot


def test(query='如何实现数据库连接', file: Optional[str] = None, repo_dir: Optional[str] = None):
    # Define the agent
    bot = init_agent_service(repo_dir=repo_dir)

    # Chat
    messages = []

    if not file:
        messages.append({'role': 'user', 'content': query})
    else:
        messages.append({'role': 'user', 'content': [{'text': query}, {'file': file}]})

    for response in bot.run(messages):
        print('bot response:', response)


def app_tui(repo_dir: Optional[str] = None):
    # Define the agent
    bot = init_agent_service(repo_dir=repo_dir)

    # Chat
    messages = []
    while True:
        # Query example: 如何实现数据库连接
        query = input('user question: ')
        # File example: path/to/context_file.py
        file = input('file url (press enter if no file): ').strip()
        if not query:
            print('user question cannot be empty！')
            continue
        if not file:
            messages.append({'role': 'user', 'content': query})
        else:
            messages.append({'role': 'user', 'content': [{'text': query}, {'file': file}]})

        response = []
        for response in bot.run(messages):
            print('bot response:', response)
        messages.extend(response)


def app_gui(repo_dir: Optional[str] = None):
    # Define the agent
    bot = init_agent_service(repo_dir=repo_dir)
    chatbot_config = {
        'prompt.suggestions': [ ]
    }
    WebUI(
        bot,
        chatbot_config=chatbot_config,
    ).run()


if __name__ == '__main__':
    # Specify repository directory (optional)
    # repo_dir = "/path/to/your/repository"
    repo_dir = DEFAULT_REPO_DIR
    
    # test(repo_dir=repo_dir)
    # app_tui(repo_dir=repo_dir)
    app_gui(repo_dir=repo_dir)