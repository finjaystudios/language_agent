from enum import StrEnum
from typing import Literal


OutputMode = Literal["stream", "ask"]


class ModeOutputConfig(StrEnum):
    translation = "stream"
    definition = "ask"
    learning = "stream"
