from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .state_machine import DialogState, DialogStateMachine


@dataclass
class Session:
    session_id: str
    domain: str = "auto"
    state_machine: DialogStateMachine = field(default_factory=DialogStateMachine)
    messages: List[Dict[str, Any]] = field(default_factory=list)
    last_extraction: Optional[Dict[str, Any]] = None
    last_results: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        now = datetime.now().isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    @property
    def state(self) -> str:
        return self.state_machine.state.value

    def touch(self):
        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "domain": self.domain,
            "state": self.state,
            "messages": self.messages[-20:],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class SessionManager:
    def __init__(self, ttl_seconds: int = 3600):
        self._sessions: Dict[str, Session] = {}
        self.ttl = ttl_seconds

    def create(self, domain: str = "auto") -> Session:
        session_id = str(uuid.uuid4())[:8]
        session = Session(session_id=session_id, domain=domain)
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Optional[Session]:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        elapsed = (datetime.now() - datetime.fromisoformat(session.updated_at)).total_seconds()
        if elapsed > self.ttl:
            del self._sessions[session_id]
            return None
        return session

    def get_or_create(self, session_id: Optional[str], domain: str = "auto") -> Session:
        if session_id:
            session = self.get(session_id)
            if session:
                # 不覆盖 domain — pipeline 会通过关键词自动检测并切换
                return session
        return self.create(domain)

    def delete(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def list_ids(self) -> List[str]:
        return list(self._sessions.keys())

    @property
    def active_count(self) -> int:
        return len(self._sessions)
