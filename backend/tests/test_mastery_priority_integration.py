import sqlite3
from datetime import date, datetime
from types import SimpleNamespace

from backend.services.review_service.review.repositories import Neo4jRepository
from backend.services.review_service.review.domain.enums import Difficulty
from backend.services.review_service.review.schemas.priority import KnowledgeStateInput, MasteryUpdateRequest, PracticeEvidence
from backend.services.review_service.review.services.priority_calculator import PriorityCalculator
from backend.services.review_service.review.services.priority_service import PriorityService
from backend.services.review_service.review.services.session_service import SessionService


def test_answer_history_builds_timed_evidence_with_error_severity(tmp_path, monkeypatch):
    database = tmp_path / "mastery.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE answer_history (student_id TEXT, question_id TEXT, is_correct INT, submitted_at TEXT, error_tags TEXT);
            CREATE TABLE question_knowledge_mapping (question_id TEXT, knowledge_id TEXT);
            CREATE TABLE review2_session (id TEXT, student_id TEXT);
            CREATE TABLE review2_attempt (
                session_id TEXT, question_id TEXT, is_correct INT, submitted_at TEXT,
                error_tags TEXT, correction_is_correct INT, correction_at TEXT,
                correction_error_tags TEXT
            );
            INSERT INTO question_knowledge_mapping VALUES ('Q1', 'K1');
            INSERT INTO answer_history VALUES ('S1', 'Q1', 0, '2026-08-19T10:00:00', '[{"level1": "概念", "confidence": 0.9}]');
            INSERT INTO answer_history VALUES ('S1', 'Q1', 1, '2026-08-20T10:00:00', NULL);
            INSERT INTO review2_session VALUES ('RS1', 'S1');
            INSERT INTO review2_attempt VALUES (
                'RS1', 'Q1', 0, '2026-08-20T11:00:00', '[{"level1": "计算"}]',
                1, '2026-08-20T11:30:00', NULL
            );
            """
        )
    monkeypatch.setattr("backend.services.review_service.review.repositories.REVIEW_DATABASE", str(database))
    repository = Neo4jRepository()
    states = repository._get_states_from_answer_history("S1")
    assert len(states) == 1
    assert [item.is_correct for item in states[0].evidence] == [False, True, False, True]
    assert states[0].evidence[0].error_severity == 0.9
    assert states[0].evidence[2].error_severity == 0.5
    assert states[0].correct_count == 2
    assert states[0].wrong_count == 2


def test_correction_evidence_works_without_answer_history(tmp_path, monkeypatch):
    database = tmp_path / "correction-only.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE answer_history (student_id TEXT, question_id TEXT, is_correct INT, submitted_at TEXT, error_tags TEXT);
            CREATE TABLE question_knowledge_mapping (question_id TEXT, knowledge_id TEXT);
            CREATE TABLE review2_session (id TEXT, student_id TEXT);
            CREATE TABLE review2_attempt (
                session_id TEXT, question_id TEXT, is_correct INT, submitted_at TEXT,
                error_tags TEXT, correction_is_correct INT, correction_at TEXT,
                correction_error_tags TEXT
            );
            INSERT INTO question_knowledge_mapping VALUES ('Q2', 'K2');
            INSERT INTO review2_session VALUES ('RS2', 'S2');
            INSERT INTO review2_attempt VALUES (
                'RS2', 'Q2', 0, '2026-08-20T09:00:00', '[{"level1": "审题"}]',
                1, '2026-08-20T09:30:00', NULL
            );
            """
        )
    monkeypatch.setattr("backend.services.review_service.review.repositories.REVIEW_DATABASE", str(database))
    states = Neo4jRepository()._get_states_from_answer_history("S2")
    assert len(states) == 1
    assert [item.is_correct for item in states[0].evidence] == [False, True]
    assert states[0].evidence[0].error_severity == 0.6


def test_question_bank_uses_sqlite_when_neo4j_is_empty(tmp_path, monkeypatch):
    database = tmp_path / "questions.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE question (
                question_id TEXT, question_description TEXT, question_type TEXT,
                difficulty TEXT, standard_solve_steps TEXT, answer TEXT
            );
            CREATE TABLE question_knowledge_mapping (
                question_id TEXT, knowledge_id TEXT, mapping_weight REAL
            );
            INSERT INTO question VALUES (
                'Q1', '25+38等于多少？', '计算题', 'medium', '25+38=63', '63'
            );
            INSERT INTO question_knowledge_mapping VALUES ('Q1', 'K1', 1.0);
            """
        )
    monkeypatch.setattr("backend.services.review_service.review.repositories.REVIEW_DATABASE", str(database))
    monkeypatch.setattr(
        "backend.services.review_service.review.repositories.neo4j_conn.query",
        lambda *_args, **_kwargs: [],
    )

    questions = Neo4jRepository().get_questions()

    assert len(questions) == 1
    assert questions[0].id == "Q1"
    assert questions[0].answer == "63"
    assert questions[0].difficulty == Difficulty.PRACTICE
    assert questions[0].knowledge[0].knowledge_point_id == "K1"
    assert questions[0].source_type == "sqlite"


class FakeRepository:
    def __init__(self, state):
        self.state = state
        self.priority_runs = {("S1", date(2026, 8, 20)): object()}
        self.saved = None

    def now(self):
        return datetime(2026, 8, 20, 12, 0, 0)

    def get_knowledge_states(self, _student_id):
        return [self.state]

    def save_mastery(self, result, state, status):
        self.saved = (result, state, status)
        return "KM1"


def test_mastery_update_uses_priority_model_and_invalidates_daily_snapshot():
    state = KnowledgeStateInput(
        student_id="S1", knowledge_point_id="K1", correct_count=1, wrong_count=2,
        correct_streak=0, wrong_streak=1, importance=70,
        evidence=[
            PracticeEvidence(is_correct=True, occurred_at=datetime(2026, 8, 18, 10)),
            PracticeEvidence(is_correct=False, occurred_at=datetime(2026, 8, 19, 10), error_severity=0.9),
            PracticeEvidence(is_correct=False, occurred_at=datetime(2026, 8, 20, 10), error_severity=0.8),
        ],
    )
    repository = FakeRepository(state)
    response = PriorityService(repository, PriorityCalculator()).update_mastery(
        MasteryUpdateRequest(student_id="S1", knowledge_id="K1", is_correct=False)
    )
    assert response.knowledge_mastery_id == "KM1"
    assert response.mastery == response.mastery_components.mastery
    assert response.master_level == round(response.mastery / 100, 4)
    assert response.priority > 50
    assert response.should_generate_review is True
    assert response.formula_version == "priority-v1.0"
    assert repository.priority_runs == {}
    assert repository.saved is not None


def test_correction_immediately_refreshes_all_related_knowledge_points():
    requests = []
    service = SessionService.__new__(SessionService)
    service.plan_service = SimpleNamespace(
        priority_service=SimpleNamespace(update_mastery=requests.append)
    )
    question = SimpleNamespace(knowledge=[
        SimpleNamespace(knowledge_point_id="K1"),
        SimpleNamespace(knowledge_point_id="K2"),
    ])
    service._refresh_mastery_after_correction("S1", question, True)
    assert [(item.knowledge_id, item.is_correct) for item in requests] == [
        ("K1", True),
        ("K2", True),
    ]
