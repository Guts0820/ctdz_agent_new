"""将 image2 题图整理结果幂等导入 Neo4j。"""

import json
from pathlib import Path
import sys
from typing import Any

SERVICE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SERVICE_DIR.parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.knowledge_graph_service.database import neo4j_conn
from backend.services.knowledge_graph_service.embedding import embed_questions


DATA_PATH = SERVICE_DIR.parents[2] / "database" / "knowledge_graph" / "image2_questions.json"


def load_questions(data_path: Path = DATA_PATH) -> list[dict[str, Any]]:
    """Load the reviewed question records without exposing source-machine paths."""
    questions = json.loads(data_path.read_text(encoding="utf-8"))
    if not isinstance(questions, list) or not questions:
        raise ValueError("题库数据必须是非空 JSON 数组。")
    ids = [str(item.get("id", "")) for item in questions]
    if any(not question_id for question_id in ids) or len(ids) != len(set(ids)):
        raise ValueError("题目 ID 不能为空且不得重复。")
    for item in questions:
        if not str(item.get("text", "")).strip() or not str(item.get("answer", "")).strip():
            raise ValueError(f"题目 {item.get('id')} 缺少题干或标准答案。")
    return questions


def build_upsert_query() -> str:
    return """
    UNWIND $items AS item
    MERGE (q:Question {id: item.id})
    SET q.text = item.text,
        q.aliases = item.aliases,
        q.answer = item.answer,
        q.answer_steps = item.answer_steps,
        q.embedding = item.embedding,
        q.type = item.type,
        q.source = item.source,
        q.image_path = item.image_path,
        q.grade = item.grade,
        q.difficulty = item.difficulty,
        q.import_batch = 'image2-v1'
    RETURN count(q) AS imported_count
    """


def import_questions(questions: list[dict[str, Any]]) -> int:
    """Create or update Question nodes by stable question ID."""
    embeddings = embed_questions(questions)
    items = [{**question, "embedding": embedding} for question, embedding in zip(questions, embeddings)]
    neo4j_conn.query(
        "CREATE CONSTRAINT question_id_unique IF NOT EXISTS "
        "FOR (q:Question) REQUIRE q.id IS UNIQUE"
    )
    result = neo4j_conn.query(build_upsert_query(), {"items": items})
    return int(result[0]["imported_count"]) if result else 0


def main() -> None:
    questions = load_questions()
    imported_count = import_questions(questions)
    print(f"已导入或更新 {imported_count} 道 image2 题目。")


if __name__ == "__main__":
    main()
