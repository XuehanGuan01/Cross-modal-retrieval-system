from __future__ import annotations

from enum import Enum
from typing import Optional


class DialogState(str, Enum):
    IDLE = "IDLE"
    EXTRACTING = "EXTRACTING"
    SEARCHING = "SEARCHING"
    PRESENTING = "PRESENTING"
    DONE = "DONE"
    REFINING = "REFINING"
    EXPANDING = "EXPANDING"
    CHATTING = "CHATTING"


VALID_TRANSITIONS = {
    DialogState.IDLE: {DialogState.EXTRACTING, DialogState.CHATTING},
    DialogState.EXTRACTING: {DialogState.SEARCHING},
    DialogState.SEARCHING: {DialogState.PRESENTING},
    DialogState.PRESENTING: {
        DialogState.DONE,
        DialogState.REFINING,
        DialogState.EXPANDING,
        DialogState.EXTRACTING,
        DialogState.SEARCHING,
        DialogState.CHATTING,
    },
    DialogState.REFINING: {DialogState.EXTRACTING},
    DialogState.EXPANDING: {DialogState.SEARCHING},
    DialogState.DONE: {DialogState.IDLE, DialogState.EXTRACTING},
    DialogState.CHATTING: {
        DialogState.EXTRACTING,
        DialogState.PRESENTING,
        DialogState.IDLE,
    },
}


class DialogStateMachine:
    def __init__(self, initial_state: DialogState = DialogState.IDLE):
        self.state = initial_state

    def transition(self, new_state: DialogState) -> bool:
        allowed = VALID_TRANSITIONS.get(self.state, set())
        if new_state not in allowed:
            return False
        self.state = new_state
        return True

    def force(self, new_state: DialogState) -> None:
        self.state = new_state

    def can_transition(self, new_state: DialogState) -> bool:
        return new_state in VALID_TRANSITIONS.get(self.state, set())

    def user_intent(self, message: str) -> Optional[DialogState]:
        text = message.strip()

        # 否定/修正类关键词优先级最高（"不对""不是"含"对""是"，先匹配）
        refine_keywords = ["不对", "不是", "再找", "重来", "重新", "换一", "改一"]
        expand_keywords = ["其他", "别的", "另外", "还有", "有没有", "更多", "扩大"]
        confirm_keywords = ["对了", "没错", "正确", "就是这个", "找到了", "第1", "第2", "第3", "第4", "第5", "第一个", "第二个", "第三个"]

        if any(kw in text for kw in refine_keywords):
            return DialogState.REFINING
        if any(kw in text for kw in expand_keywords):
            return DialogState.EXPANDING
        if any(kw in text for kw in confirm_keywords):
            return DialogState.DONE
        return None
