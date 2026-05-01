from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from prompts.resume_prompt import RESUME_WRITER_PERSONA

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

prompt = ChatPromptTemplate.from_messages([
    ("system", RESUME_WRITER_PERSONA),
    ("human", "{job_description}")
])


def introduce_context(state):
    chain = prompt | llm
    result = chain.invoke({"job_description": state.job_description})

    # save context
    state.job_context = result.content
    return state