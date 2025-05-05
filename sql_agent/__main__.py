from common.server import A2AServer
from common.types import AgentCard, AgentCapabilities, AgentSkill, MissingAPIKeyError
from task_manager import AgentTaskManager
from agent import SQLAgent
import click
import os
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@click.command()
@click.option("--host", default="localhost")
@click.option("--port", default=10002)
def main(host, port):
    try:
        capabilities = AgentCapabilities(streaming=True)
        skill = AgentSkill(
            id="sql_agent",
            name="SQL Agent",
            description="Help with writing SQL query",
            tags=["sql"],
            examples=["Can you write a SQL query to get the total salary of the employees?"],
        )
        agent_card = AgentCard(
            name="SQL Agent",
            description="This agent handles writing SQL queries to retrieve data from a SQL database.",
            url=f"http://{host}:{port}/",
            version="1.0.0",
            defaultInputModes=SQLAgent.SUPPORTED_CONTENT_TYPES,
            defaultOutputModes=SQLAgent.SUPPORTED_CONTENT_TYPES,
            capabilities=capabilities,
            skills=[skill],
        )
        server = A2AServer(
            agent_card=agent_card,
            task_manager=AgentTaskManager(agent=SQLAgent()),
            host=host,
            port=port,
        )
        server.start()
    except MissingAPIKeyError as e:
        logger.error(f"Error: {e}")
        exit(1)
    except Exception as e:
        logger.error(f"An error occurred during server startup: {e}")
        exit(1)
    
if __name__ == "__main__":
    main()