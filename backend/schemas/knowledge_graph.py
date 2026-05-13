from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel


# semantic categories of nodes
NodeType = Literal[
    "person",          # only 1 per graph
    "job",             # only 1 per graph
    "company",
    "keyword",         # raw key phrases extracted from the resume or job description
    "canonical_skill", # skills canonicalized from keywords or person skills; used as a shared vocabulary that lets job requirements and resume speak the same language
    "person_skill",    # skills extracted from the resume
    "education",
    "experience",
    "project",
    "certification",
]


# node object
class KGNode(BaseModel):
    id: str                                # unique identifier used to connect this node with edges
    type: NodeType                         # node type
    label: str                             # node name
    meta: Optional[Dict[str, Any]] = None  # extra information, e.g. kind, raw text, source section, dates


# edge object
class KGEdge(BaseModel):
    source: str                            # source node id
    target: str                            # target node id
    relation: str                          # relationship name describing how the two nodes are connected, e.g. 'requires', 'matches', 'supports', 'canonicalizes_to'
    weight: float = 1.0                    # strength of the connection "If this edge exists, how important is it?"  [unused]
    confidence: float = 1.0                # confidence in the connection "Should this edge exist?"                  [unused]
    evidence: Optional[str] = None         # additional text that supports this edge                                 [unused]
    provenance: Optional[str] = None       # where the edge came from, e.g. 'rule', 'llm', 'manual', 'hybrid'        [unused]
    meta: Optional[Dict[str, Any]] = None  # extra information (?)


class KnowledgeGraph(BaseModel):
    nodes: List[KGNode]
    edges: List[KGEdge]
    meta: Optional[Dict[str, Any]] = None  # graph-level information (do we need it ?)