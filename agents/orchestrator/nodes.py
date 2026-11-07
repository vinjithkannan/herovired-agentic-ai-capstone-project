from agents.orchestrator.state import RequirementState

def intake_node(state: RequirementState) -> RequirementState:
    # Phase 1 placeholder: normalize incoming requirement text.
    text = state.get("original_requirement", "").strip()
    return {
        **state,
        "original_requirement": text,
        "execution_log": state.get("execution_log", []) + [
            {"node": "intake", "status": "completed"}
        ],
    }
