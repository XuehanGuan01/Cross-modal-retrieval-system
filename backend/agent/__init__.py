# Agent module — lazy imports to avoid circular / missing dep issues.

def __getattr__(name):
    if name == "AgentPipeline":
        from .pipeline import AgentPipeline
        return AgentPipeline
    if name == "create_llm":
        from .llm_factory import create_llm
        return create_llm
    if name == "build_prompt":
        from .prompts import build_prompt
        return build_prompt
    if name == "DOMAIN_AGENT_CONFIG":
        from .prompts import DOMAIN_AGENT_CONFIG
        return DOMAIN_AGENT_CONFIG
    if name == "DialogState":
        from .state_machine import DialogState
        return DialogState
    if name == "DialogStateMachine":
        from .state_machine import DialogStateMachine
        return DialogStateMachine
    if name == "SessionManager":
        from .session_manager import SessionManager
        return SessionManager
    if name == "DomainAgent":
        from .domain_agent import DomainAgent
        return DomainAgent
    raise AttributeError(f"module 'agent' has no attribute '{name}'")
