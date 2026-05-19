from dataclasses import dataclass, field


@dataclass
class ConversationTurn:
    user_input: str
    assistant_reply: str


@dataclass
class ConversationMemory:
    max_turns: int = 5
    turns: list[ConversationTurn] = field(default_factory=list)

    def add_turn(self, user_input: str, assistant_reply: str) -> None:
        self.turns.append(
            ConversationTurn(
                user_input=user_input,
                assistant_reply=assistant_reply,
            )
        )

        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns :]

    def format_for_prompt(self) -> str:
        if not self.turns:
            return "No previous conversation."

        formatted_turns = []

        for index, turn in enumerate(self.turns, start=1):
            formatted_turns.append(
                f"""
                Turn {index}
                User: {turn.user_input}
                Assistant: {turn.assistant_reply}
                """.strip()
            )

        return "\n\n".join(formatted_turns)
