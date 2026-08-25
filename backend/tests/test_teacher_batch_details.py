def test_list_batches_includes_question_details(tmp_path, monkeypatch):
    from backend.services.teacher_service import database, homework_batch_service

    database.DATABASE_PATH = str(tmp_path / "batch-details.db")
    with database.get_teacher_db() as connection:
        connection.executescript(
            """
            CREATE TABLE homework_batch (
                batch_id TEXT PRIMARY KEY, class_id TEXT, teacher_id TEXT,
                batch_date TEXT, release_status TEXT, created_at TEXT
            );
            CREATE TABLE homework_batch_question (batch_id TEXT, question_id TEXT);
            CREATE TABLE question (
                question_id TEXT PRIMARY KEY, question_description TEXT, answer TEXT
            );
            CREATE TABLE question_knowledge_mapping (question_id TEXT, knowledge_id TEXT);
            INSERT INTO homework_batch VALUES ('HB-1', 'C1', 'T1', '2026-08-25', 'locked', '2026-08-25');
            INSERT INTO homework_batch_question VALUES ('HB-1', 'Q1');
            INSERT INTO question VALUES ('Q1', '0.8 × 0.02 =', '0.016');
            INSERT INTO question_knowledge_mapping VALUES ('Q1', 'K167');
            """
        )
        connection.commit()

    monkeypatch.setattr(homework_batch_service, "get_teacher_db", database.get_teacher_db)
    result = homework_batch_service.list_batches(teacher_id="T1")
    assert result.data[0].question_details == [{
        "question_id": "Q1", "text": "0.8 × 0.02 =", "answer": "0.016", "knowledge_id": "K167"
    }]


def test_list_batches_falls_back_when_question_tables_are_missing(tmp_path, monkeypatch):
    from backend.services.teacher_service import database, homework_batch_service

    database.DATABASE_PATH = str(tmp_path / "batch-legacy.db")
    with database.get_teacher_db() as connection:
        connection.executescript(
            """
            CREATE TABLE homework_batch (
                batch_id TEXT PRIMARY KEY, class_id TEXT, teacher_id TEXT,
                batch_date TEXT, release_status TEXT, created_at TEXT
            );
            CREATE TABLE homework_batch_question (batch_id TEXT, question_id TEXT);
            INSERT INTO homework_batch VALUES ('HB-1', 'C1', 'T1', '2026-08-25', 'locked', '2026-08-25');
            INSERT INTO homework_batch_question VALUES ('HB-1', 'Q1');
            """
        )
        connection.commit()

    monkeypatch.setattr(homework_batch_service, "get_teacher_db", database.get_teacher_db)
    result = homework_batch_service.list_batches()
    assert result.data[0].question_details[0]["question_id"] == "Q1"


def test_student_batches_include_locked_questions_without_standard_answers(tmp_path, monkeypatch):
    from backend.services.teacher_service import database, homework_batch_service

    database.DATABASE_PATH = str(tmp_path / "student-batches.db")
    with database.get_teacher_db() as connection:
        connection.executescript(
            """
            CREATE TABLE homework_batch (
                batch_id TEXT PRIMARY KEY, class_id TEXT, teacher_id TEXT,
                batch_date TEXT, release_status TEXT, created_at TEXT
            );
            CREATE TABLE homework_batch_question (batch_id TEXT, question_id TEXT);
            CREATE TABLE question (
                question_id TEXT PRIMARY KEY, question_description TEXT, answer TEXT
            );
            CREATE TABLE question_knowledge_mapping (question_id TEXT, knowledge_id TEXT);
            INSERT INTO homework_batch VALUES ('HB-LOCKED', '一(1)班', 'T1', '2026-08-25', 'locked', '2026-08-25');
            INSERT INTO homework_batch_question VALUES ('HB-LOCKED', 'Q1');
            INSERT INTO question VALUES ('Q1', '2 + 3 =', '5');
            INSERT INTO question_knowledge_mapping VALUES ('Q1', 'K001');
            """
        )
        connection.commit()

    monkeypatch.setattr(homework_batch_service, "get_teacher_db", database.get_teacher_db)
    result = homework_batch_service.list_student_batches("一(1)班")
    question = result["data"][0]["question_details"][0]
    assert result["data"][0]["release_status"] == "locked"
    assert question == {"question_id": "Q1", "text": "2 + 3 =", "knowledge_id": "K001"}


def test_list_batches_backfills_missing_sqlite_question_from_knowledge_graph(tmp_path, monkeypatch):
    from backend.services.teacher_service import database, homework_batch_service

    database.DATABASE_PATH = str(tmp_path / "batch-graph-detail.db")
    with database.get_teacher_db() as connection:
        connection.executescript(
            """
            CREATE TABLE homework_batch (batch_id TEXT PRIMARY KEY, class_id TEXT, teacher_id TEXT, batch_date TEXT, release_status TEXT, created_at TEXT);
            CREATE TABLE homework_batch_question (batch_id TEXT, question_id TEXT);
            CREATE TABLE question (question_id TEXT PRIMARY KEY, question_description TEXT, answer TEXT);
            CREATE TABLE question_knowledge_mapping (question_id TEXT, knowledge_id TEXT);
            INSERT INTO homework_batch VALUES ('HB-1', 'C1', 'T1', '2026-08-25', 'locked', '2026-08-25');
            INSERT INTO homework_batch_question VALUES ('HB-1', 'Q-GRAPH');
            """
        )
        connection.commit()

    class GraphResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"text": "0.24 × 20 =", "answer": "4.8", "knowledge_id": "K168"}

    monkeypatch.setattr(homework_batch_service, "get_teacher_db", database.get_teacher_db)
    monkeypatch.setattr(homework_batch_service.requests, "get", lambda *args, **kwargs: GraphResponse())
    result = homework_batch_service.list_batches()
    assert result.data[0].question_details[0] == {
        "question_id": "Q-GRAPH", "text": "0.24 × 20 =", "answer": "4.8", "knowledge_id": "K168"
    }
