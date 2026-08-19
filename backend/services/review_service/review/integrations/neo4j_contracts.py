from datetime import datetime, timedelta
from typing import Union

from backend.shared.neo4j_connection import neo4j_conn
from backend.services.review_service.review.schemas.priority import KnowledgeStateInput, PracticeEvidence


class Neo4jKnowledgeStateClient:
    def get_states(self, student_id: Union[int, str]) -> list[KnowledgeStateInput]:
        query = """
        MATCH (a:AnswerHistory)-[:ANSWERED_QUESTION]->(q:Question)-[:EXAMINES]->(kp:KnowledgePoint)
        WHERE a.student_id = $student_id
        RETURN kp.id AS knowledge_id,
               kp.name AS title,
               collect({
                   is_correct: a.is_correct,
                   occurred_at: a.answered_at,
                   error_severity: CASE WHEN a.is_correct = false THEN 0.5 ELSE 0 END
               }) AS evidence_list,
               sum(CASE WHEN a.is_correct THEN 1 ELSE 0 END) AS correct_count,
               sum(CASE WHEN NOT a.is_correct THEN 1 ELSE 0 END) AS wrong_count
        """
        try:
            results = neo4j_conn.query(query, {"student_id": str(student_id)})
        except Exception as e:
            print(f"Error querying knowledge states: {e}")
            return self._get_fallback_states(student_id)

        states = []
        for row in results:
            evidence_list = row.get("evidence_list", [])

            practice_evidence = []
            for ev in evidence_list:
                if ev.get("occurred_at"):
                    occurred_at = ev["occurred_at"]
                    if isinstance(occurred_at, str):
                        occurred_at = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
                    elif hasattr(occurred_at, "to_native"):
                        occurred_at = occurred_at.to_native()
                    elif hasattr(occurred_at, "year"):
                        occurred_at = datetime(
                            occurred_at.year, occurred_at.month, occurred_at.day,
                            getattr(occurred_at, 'hour', 0), getattr(occurred_at, 'minute', 0),
                            getattr(occurred_at, 'second', 0)
                        )
                else:
                    occurred_at = datetime.now()

                severity = ev.get("error_severity")
                if severity and severity > 0:
                    severity = min(1.0, severity)
                else:
                    severity = None

                practice_evidence.append(PracticeEvidence(
                    is_correct=ev.get("is_correct") if ev.get("is_correct") is not None else True,
                    occurred_at=occurred_at,
                    error_severity=severity,
                ))

            practice_evidence.sort(key=lambda x: x.occurred_at)

            if practice_evidence:
                correct_count = sum(1 for e in practice_evidence if e.is_correct)
                wrong_count = sum(1 for e in practice_evidence if not e.is_correct)
            else:
                correct_count = row.get("correct_count", 0) or 0
                wrong_count = row.get("wrong_count", 0) or 0

            correct_streak = 0
            wrong_streak = 0
            for ev in reversed(practice_evidence):
                if ev.is_correct:
                    if wrong_streak > 0:
                        break
                    correct_streak += 1
                else:
                    if correct_streak > 0:
                        break
                    wrong_streak += 1

            importance = 50.0

            state = KnowledgeStateInput(
                student_id=str(student_id),
                knowledge_point_id=row["knowledge_id"],
                correct_count=correct_count,
                wrong_count=wrong_count,
                correct_streak=correct_streak,
                wrong_streak=wrong_streak,
                evidence=practice_evidence,
                importance=importance,
                state_version=1,
            )
            states.append(state)

        if not states:
            return self._get_fallback_states(student_id)

        return states

    def _get_fallback_states(self, student_id: Union[int, str]) -> list[KnowledgeStateInput]:
        query = """
        MATCH (kp:KnowledgePoint)
        RETURN kp.id AS knowledge_id, kp.name AS title
        LIMIT 20
        """
        try:
            results = neo4j_conn.query(query, {})
        except Exception:
            return []

        states = []
        for row in results:
            state = KnowledgeStateInput(
                student_id=str(student_id),
                knowledge_point_id=row["knowledge_id"],
                correct_count=0,
                wrong_count=0,
                correct_streak=0,
                wrong_streak=0,
                evidence=[],
                importance=50.0,
                state_version=1,
            )
            states.append(state)
        return states

    def apply_attempt_evidence(self, event: dict) -> None:
        # 用 MERGE 而不是 MATCH：如果 Student/Question 节点不存在，创建 stub 节点
        # 避免 MATCH 返回 0 行时后续 MERGE/SET 静默不执行的问题
        query = """
        MERGE (s:Student {id: $student_id})
        MERGE (q:Question {id: $question_id})
        MERGE (s)-[r:ANSWERED_QUESTION]->(q)
        SET r.is_correct = $is_correct,
            r.answered_at = $answered_at,
            r.selected_option = $selected_option,
            r.error_severity = $error_severity
        RETURN r
        """
        params = {
            "student_id": str(event.get("student_id", "")),
            "question_id": event.get("question_id", ""),
            "is_correct": event.get("is_correct", False),
            "answered_at": datetime.now().isoformat(),
            "selected_option": event.get("selected_option", 0),
            "error_severity": event.get("error_severity"),
        }
        try:
            result = neo4j_conn.query(query, params)
            if not result:
                raise RuntimeError(
                    f"apply_attempt_evidence wrote 0 rows for student_id={params['student_id']}, "
                    f"question_id={params['question_id']} — this should not happen after MERGE"
                )
        except Exception as e:
            # 不再静默吞掉，重新抛出让上层决定如何处理
            raise RuntimeError(f"Failed to apply attempt evidence to Neo4j: {e}") from e


class Neo4jKnowledgeGraphClient:
    def get_question_mapping(self, question_id: str) -> list[dict]:
        query = """
        MATCH (q:Question {id: $question_id})-[r:EXAMINES]->(kp:KnowledgePoint)
        RETURN kp.id AS knowledge_id, kp.name AS title, r.weight AS weight
        """
        try:
            results = neo4j_conn.query(query, {"question_id": question_id})
            return results
        except Exception as e:
            print(f"Error getting question mapping: {e}")
            return []


class StubAIGradingClient:
    def request_grading(self, attempt: dict) -> str:
        return "PENDING"
