from datetime import date

from backend.services.review_service.review.repositories import Neo4jRepository
from backend.services.review_service.review.schemas.priority import MasteryUpdateRequest, MasteryUpdateResponse, PriorityRunResponse
from backend.services.review_service.review.services.priority_calculator import PriorityCalculator


class PriorityService:
    def __init__(self, repository: Neo4jRepository, calculator: PriorityCalculator) -> None:
        self.repository = repository
        self.calculator = calculator

    def run_for_student(self, student_id: str, business_date: date | None = None) -> PriorityRunResponse:
        target_date = business_date or self.repository.now().date()
        key = (student_id, target_date)
        existing = self.repository.priority_runs.get(key)
        if existing:
            return existing.model_copy(update={"created": False})

        states = self.repository.get_knowledge_states(student_id)
        if not states:
            states = self.repository._get_fallback_states(student_id)

        if not states:
            raise LookupError(f"未找到学生 {student_id} 的知识状态")

        calculated_at = self.repository.now()
        results = [
            self.calculator.calculate(state, target_date, calculated_at)
            for state in states
        ]
        results.sort(key=lambda item: item.priority, reverse=True)
        response = PriorityRunResponse(
            run_id=self.repository.new_id("priority"),
            student_id=student_id,
            business_date=target_date,
            results=results,
            formula_version="priority-v1.0",
            created=True,
        )
        self.repository.priority_runs[key] = response
        return response

    def update_mastery(self, request: MasteryUpdateRequest) -> MasteryUpdateResponse:
        target_date = self.repository.now().date()
        self.repository.priority_runs.pop((request.student_id, target_date), None)
        states = self.repository.get_knowledge_states(request.student_id)
        state = next((item for item in states if item.knowledge_point_id == request.knowledge_id), None)
        if state is None:
            raise LookupError(f"未找到知识点 {request.knowledge_id} 的答题证据")
        result = self.calculator.calculate(state, target_date, self.repository.now())
        if result.mastery.mastery >= 80:
            mastery_status = "mastered"
            next_action = "complete"
        elif result.mastery.mastery < 40:
            mastery_status = "weak"
            next_action = "teacher_intervention"
        else:
            mastery_status = "pending"
            next_action = "basic_practice" if result.mastery.mastery < 60 else "practice"
        mastery_id = self.repository.save_mastery(result, state, mastery_status)
        return MasteryUpdateResponse(
            knowledge_mastery_id=mastery_id,
            master_level=round(result.mastery.mastery / 100, 4),
            mastery=result.mastery.mastery,
            priority=result.priority,
            mastery_status=mastery_status,
            next_action=next_action,
            correct_count=state.correct_count,
            wrong_count=state.wrong_count,
            should_generate_review=(not request.is_correct or result.priority >= 50),
            components=result.components,
            mastery_components=result.mastery,
            formula_version=result.formula_version,
        )
