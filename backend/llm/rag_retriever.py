import json
from typing import Any, Dict, List

from langchain_chroma import Chroma


def build_rag_query(job_details: Dict[str, Any]) -> str:
    query_parts: List[str] = []

    # all structured fields from the JobDetails schema
    job_details_fields = [
        "job_title",
        "job_purpose",
        "keywords",
        "job_duties_and_responsibilities",
        "required_qualifications",
        "preferred_qualifications",
        "company_name",
        "company_details",
    ]

    for field in job_details_fields:
        value = job_details.get(field)

        # skip empty fields to avoid adding noise to the retrieval query
        if not value:
            continue
        
        # if the field is a list, append each element separately
        # if the field is a dictionary (nested structured data), convert it into a JSON string so we do not lose any information
        # for simple values (strings, numbers, etc.), just convert them to string and append
        if isinstance(value, list):
            query_parts.extend([str(x) for x in value if x])
        elif isinstance(value, dict):
            query_parts.append(json.dumps(value, ensure_ascii=False))
        else:
            query_parts.append(str(value))

    # combine all extracted "signals" into a single query string
    return "\n".join(query_parts) if query_parts else ""


def retrieve_rag_context(vector_db: Chroma, job_details: Dict[str, Any], k: int = 8) -> Dict[str, Any]:
    # build a text query from job description
    query = build_rag_query(job_details)

    # convert query into embedding vector and search top-k similar documents from the vector database using cosine similarity
    # (these documents are text chunks from resumes that are most relevant to the job, represented as LangChain Document objects)
    docs = vector_db.similarity_search(query, k=k)

    retrieved = []

    for d in docs:
        retrieved.append({
            "content": d.page_content, # actual resume text chunk
            "metadata": d.metadata, # source info like file name, page number, etc.
        })

    return {
        "rag_query": query,
        "retrieved_chunks": retrieved,
        "retrieved_count": len(retrieved),
    }