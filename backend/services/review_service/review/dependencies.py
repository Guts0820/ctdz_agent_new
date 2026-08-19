from backend.services.review_service.review.repositories import Neo4jRepository
from backend.services.review_service.review.services.plan_service import PlanService
from backend.services.review_service.review.services.priority_calculator import priority_calculator
from backend.services.review_service.review.services.priority_service import PriorityService
from backend.services.review_service.review.services.question_selector import question_selector
from backend.services.review_service.review.services.session_service import SessionService

repository = Neo4jRepository()
priority_service = PriorityService(repository, priority_calculator)
plan_service = PlanService(repository, priority_service, question_selector)
session_service = SessionService(repository, plan_service)
