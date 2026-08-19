"""为 Neo4j 中已有 Question 节点生成 Qwen Embedding。"""

from pathlib import Path
import sys

SERVICE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SERVICE_DIR.parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.knowledge_graph_service.database import neo4j_conn
from backend.services.knowledge_graph_service.embedding import embed_questions


def build_backfill_query() -> str:
    return """
    UNWIND $items AS item
    MATCH (q:Question {id: item.id})
    SET q.embedding = item.embedding
    RETURN count(q) AS updated_count
    """


def backfill_question_embeddings() -> int:
    rows = neo4j_conn.query(
        "MATCH (q:Question) RETURN q.id AS id, q.text AS text, "
        "q.aliases AS aliases, q.explanation AS explanation"
    )
    questions = [dict(row) for row in rows if str(row.get("id", "")).strip()]
    if not questions:
        return 0
    embeddings = embed_questions(questions)
    if not any(embeddings):
        raise RuntimeError("Qwen Embedding 未配置，无法为已有题目生成向量。")
    items = [
        {"id": question["id"], "embedding": embedding}
        for question, embedding in zip(questions, embeddings)
        if embedding
    ]
    result = neo4j_conn.query(build_backfill_query(), {"items": items})
    return int(result[0]["updated_count"]) if result else 0


def main() -> None:
    print(f"已更新 {backfill_question_embeddings()} 道题目的 embedding。")


if __name__ == "__main__":
    main()
