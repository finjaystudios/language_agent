from models.prompt_schemas import SessionState
from orchestration.modes.translation import TranslationHandler
from orchestration.modes.definition import DefinitionHandler
from orchestration.modes.learning import LearningHandler


class SessionOrchestrator:
    def __init__(self, llm_service, router, memory):
        self.llm_service = llm_service
        self.router = router
        self.memory = memory
        self.session = SessionState()

        self.handlers = {
            "translation": TranslationHandler(llm_service),
            "definition": DefinitionHandler(llm_service),
            "learning": LearningHandler(llm_service),
        }

    def handle_turn(self, user_input: str) -> dict:
        history = self.memory.format_for_prompt()

        intent = self.router.classify(
            user_input=user_input,
            session=self.session,
            conversation_history=history,
        )

        self.session = self.router.apply_intent(self.session, intent)

        if intent.confidence == "low" and intent.clarification_question:
            response = {
                "mode": self.session.active_mode,
                "response": intent.clarification_question,
                "intent": intent.model_dump(),
            }
            self.memory.add_turn(user_input, response["response"])
            return response

        handler = self.handlers.get(self.session.active_mode)

        if handler is None:
            response = {
                "mode": "general",
                "response": "I can help with translation, definitions, or language learning. Which would you like?",
                "intent": intent.model_dump(),
            }
            self.memory.add_turn(user_input, response["response"])
            return response

        response = handler.handle(
            user_input=user_input,
            session=self.session,
            conversation_history=history,
        )

        response["intent"] = intent.model_dump()
        self.memory.add_turn(user_input, response["response"])

        return response