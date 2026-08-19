from datetime import date

from backend.services.review_service.review.repositories import Neo4jRepository
from backend.services.review_service.review.schemas.priority import PriorityRunResponse
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
