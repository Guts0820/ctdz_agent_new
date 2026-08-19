import re

from backend.services.knowledge_graph_service.database import neo4j_conn
from backend.shared.config import KG_VECTOR_INDEX_NAME, QWEN_EMBEDDING_DIMENSIONS


def build_vector_index_query() -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", KG_VECTOR_INDEX_NAME):
        raise ValueError("KG_VECTOR_INDEX_NAME must be a valid Neo4j identifier")
    return f"""
    CREATE VECTOR INDEX {KG_VECTOR_INDEX_NAME} IF NOT EXISTS
    FOR (q:Question) ON (q.embedding)
    OPTIONS {{indexConfig: {{
        `vector.dimensions`: {QWEN_EMBEDDING_DIMENSIONS},
        `vector.similarity_function`: 'cosine'
    }}}}
    """


def ensure_vector_index() -> None:
    """Create the configured Neo4j vector index when the server supports it."""
    neo4j_conn.query(build_vector_index_query())
