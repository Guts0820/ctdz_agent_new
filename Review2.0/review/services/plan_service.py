from datetime import date

from review.domain.enums import ItemStatus, PlanMode, PlanStatus
from review.repositories import Neo4jRepository
from review.schemas.review import CreateReviewPlanRequest, ReviewPlan, UpdatePlanCapacityRequest
from review.services.priority_service import PriorityService
from review.services.question_selector import QuestionSelector

DAILY_QUESTION_LIMIT = 10
DAILY_TIME_LIMIT_MINUTES = 20


class PlanService:
    def __init__(
        self,
        repository: Neo4jRepository,
        priority_service: PriorityService,
        selector: QuestionSelector,
    ) -> None:
        self.repository = repository
        self.priority_service = priority_service
        self.selector = selector

    def create(self, request: CreateReviewPlanRequest) -> ReviewPlan:
        business_date = request.business_date or self.repository.now().date()
        # 原型阶段：每次都创建新计划，不查重

        priority_run = self.priority_service.run_for_student(request.student_id, business_date)
        questions = self.repository.get_questions()
        if not questions:
            raise LookupError("题库为空，无法生成复习计划")

        # 每日配额封顶：不管调用方传多大，最终取较小值
        final_count = min(request.question_count or DAILY_QUESTION_LIMIT, DAILY_QUESTION_LIMIT)
        final_time = min(request.time_limit_minutes or DAILY_TIME_LIMIT_MINUTES, DAILY_TIME_LIMIT_MINUTES) if request.time_limit_minutes else None

        items = self.selector.select(
            questions,
            priority_run.results,
            request.mode,
            final_count,
            final_time,
        )

        if not items:
            fallback_qs = self.repository._get_fallback_questions()
            items = self.selector.select(
                fallback_qs,
                priority_run.results,
                request.mode,
                final_count,
                final_time,
            )

        plan = ReviewPlan(
            id=self.repository.new_id("plan"),
            student_id=request.student_id,
            business_date=business_date,
            mode=request.mode,
            question_count=final_count if request.mode == PlanMode.QUESTION_COUNT else len(items),
            time_limit_minutes=final_time,
            priority_run_id=priority_run.run_id,
            status=PlanStatus.NOT_STARTED,
            items=items,
            created_at=self.repository.now(),
            planning_config_version="planning-demo-v1",
        )
        self.repository.save_plan(plan)
        return plan

    def get(self, plan_id: str) -> ReviewPlan:
        plan = self.repository.get_plan_by_id(plan_id)
        if not plan:
            raise LookupError("复习计划不存在")
        return plan

    def update_capacity(self, plan_id: str, request: UpdatePlanCapacityRequest) -> ReviewPlan:
        plan = self.get(plan_id)
        if plan.mode != PlanMode.QUESTION_COUNT:
            raise ValueError("V1仅支持修改按题量计划")
        completed = [item for item in plan.items if item.status == ItemStatus.COMPLETED]
        current = [item for item in plan.items if item.status == ItemStatus.CURRENT]
        minimum = len(completed) + len(current)
        if request.question_count < minimum:
            raise ValueError(f"题量不能小于已完成和当前题数量{minimum}")

        priority_run = self.repository.priority_runs.get((plan.student_id, plan.business_date))
        if not priority_run:
            raise LookupError("优先级快照不存在，请先创建优先级快照")

        fixed = completed + current
        fixed_ids = {item.question_id for item in fixed}
        covered = {knowledge_id for item in fixed for knowledge_id in item.knowledge_point_ids}
        remaining_count = request.question_count - len(fixed)
        new_items = self.selector.select(
            self.repository.get_questions(),
            priority_run.results,
            PlanMode.QUESTION_COUNT,
            remaining_count,
            None,
            excluded_question_ids=fixed_ids,
            already_covered=covered,
        )
        plan.items = fixed + new_items
        for position, item in enumerate(plan.items, start=1):
            item.position = position
        plan.question_count = len(plan.items)
        self.repository.save_plan(plan)
        return plan