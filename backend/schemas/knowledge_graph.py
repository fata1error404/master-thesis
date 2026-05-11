from pydantic import BaseModel
from typing import List, Literal, Optional


NodeType = Literal[
    "job",
    "skill",
    "experience",
    "project",
    "education",
    "company",
    "certification",
    "keyword"
]


class KGNode(BaseModel):
    id: str
    type: NodeType
    label: str
    meta: Optional[dict] = None


class KGEdge(BaseModel):
    source: str
    target: str
    relation: str


class KnowledgeGraph(BaseModel):
    nodes: List[KGNode]
    edges: List[KGEdge]