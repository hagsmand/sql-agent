import datetime
from zoneinfo import ZoneInfo
from google.adk.agents import Agent, LlmAgent, SequentialAgent
from google.adk.models.lite_llm import LiteLlm
from task_manager import AgentWithTaskManager
from google.adk.runners import Runner
from google.adk.artifacts import InMemoryArtifactService
from google.adk.sessions import InMemorySessionService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService


def get_schema() -> str:
    return """
    CREATE TABLE `milvus_sales` (
        `id` int(11) NOT NULL AUTO_INCREMENT,
        `customer_email` varchar(255) NOT NULL,
        `customer_name` varchar(255) NOT NULL,
        `customer_phone` varchar(255) NOT NULL,
        `customer_address` varchar(255) NOT NULL,
        `customer_city` varchar(255) NOT NULL,
        `customer_state` varchar(255) NOT NULL,
        `customer_zip` varchar(255) NOT NULL,
        `customer_country` varchar(255) NOT NULL,
        `customer_created_at` datetime NOT NULL,
        `customer_updated_at` datetime NOT NULL,
        `customer_deleted_at` datetime NOT NULL,
        `customer_deleted` tinyint(1) NOT NULL,
        `customer_status` varchar(255) NOT NULL,
        `customer_source` varchar(255) NOT NULL,
        `customer_lead_source` varchar(255) NOT NULL,
        `customer_lead_source_detail` varchar(255) NOT NULL,
    )"""


# SQL schema analyzer -> SQL writer agent -> SQL refactor agent
schema_analyzer_agent = LlmAgent(
    name="sql_schema_analyzer",
    model=LiteLlm(model="groq/meta-llama/llama-4-scout-17b-16e-instruct"),
    description=(
        "SQL schema analyzer agent that can analyse SQL schema based on human input by looking at the schema and the question."
    ),
    output_key='query_plan',
    tools=[get_schema],
    instruction=(
        """
        You are a SQL schema analyzer agent. You must use 'get_schema' tool to see database schema and analyze it with user's question. You will analyze the SQL schema and the question and return XML of field and query plan that potentially be used to answer the question.
        For example: 
        SQL schema:
        CREATE TABLE `pets` (
            `id` int(11) NOT NULL AUTO_INCREMENT,
            `name` varchar(255) NOT NULL,
            `breed` varchar(255) NOT NULL,
            `age` int(11) NOT NULL,
            `owner_id` int(11) NOT NULL,
            PRIMARY KEY (`id`)
        )
        
        **Question:**
        What is the average age of pets with breed Labrador whose name contain 'ky'?
        
        **output:**
        You will return XML of fields, tables, and query plan that potentially be used to answer the question.
        For example:
        <field>
            <1>age</1>
            <2>breed</2>
            <3>name</3>
        </field>
        <table>
            <1>pets</1>
        </table>
        <query_plan>
            <1>Filter by breed Labrador</1>
            <2>Filter by name contain 'ky'</2>
            <3>Calculate average age</3>
        </query_plan>
        """
    ),
)

sql_writer_agent = LlmAgent(
    name="sql_writer",
    model=LiteLlm(model="groq/meta-llama/llama-4-scout-17b-16e-instruct"),
    description=(
        "SQL writer agent"
    ),
    output_key='sql_output',
    instruction=(
        """ You are an SQL expert you will be given an XML that guide you what field and query plan to use together with user's question. You will write SQL query based on the XML and user's question.
        For example:
        XML of query plan:
        <field>
            <1>age</1>
            <2>breed</2>
            <3>name</3>
        </field>
        <query_plan>
            <1>Filter by breed Labrador</1>
            <2>Filter by name contain 'ky'</2>
            <3>Calculate average age</3>
        </query_plan>
        
        **User's question:**
        What is the average age of pets with breed Labrador whose name contain 'ky'?
        
        **output:**
        You will return SQL query that potentially be used to answer the question.
        For example:
        SELECT AVG(age) FROM pets WHERE breed = 'Labrador' AND name LIKE '%ky%'
        
        **XML of query plan**
        {query_plan}
        """ 
    )
)

sql_refactor_agent = LlmAgent(
    name="sql_refactor",
    model=LiteLlm(model="groq/meta-llama/llama-4-scout-17b-16e-instruct"),
    description=(
        "SQL refactor agent"
    ),
    output_key='refactored_sql_output',
    instruction=(
        """
        You are an SQL expert. You will be given a SQL query, XML of query plan with related field, tables, and user's question that potentially be used to answer the question. You will refactor the SQL query to make it more efficient.
        
        For example:
        **User's question:**
        What is the average age of pets with breed Labrador whose name contain 'ky'?

        **SQL query:**
        SELECT AVG(age), name, breed FROM pets WHERE breed = 'Labrador' AND name LIKE '%ky%'
        **XML of query plan**
        <field>
            <1>age</1>
            <2>breed</2>
            <3>name</3>
        </field>
        <query_plan>
            <1>Filter by breed Labrador</1>
            <2>Filter by name contain 'ky'</2>
            <3>Calculate average age</3>
        </query_plan>

        **output:**
        You will return SQL query that potentially be used to answer the question.
        For example:
        SELECT AVG(age) FROM pets WHERE breed = 'Labrador' AND name LIKE '%ky%'

        **SQL query:**
        {sql_output}
        **XML of query plan**
        {query_plan}
        """
    )
)


class SQLAgent(AgentWithTaskManager):
    """An agent that handles generating SQL queries."""
    
    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

    def __init__(self):
        self._agent = self._build_agent()
        self._user_id = "remote_agent"
        self._runner = Runner(
            app_name=self._agent.name,
            agent=self._agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )
    
    def _build_agent(self) -> SequentialAgent:
        """Builds the LLM agent for writing SQL query."""
        return SequentialAgent(
            name="SQLCodePipelineAgent",
            sub_agents=[schema_analyzer_agent, sql_writer_agent, sql_refactor_agent],
            description="Executes a sequence of SQL analyzer, reviewing, and refactoring.",
        )
