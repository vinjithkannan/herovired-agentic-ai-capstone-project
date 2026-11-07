from langgraph.graph import END, START, StateGraph
from agents.orchestrator.nodes import intake_node
from agents.orchestrator.state import RequirementState

def build_graph():
    # Add specialized agent nodes, conditional edges and approval interrupts in later phases.
    graph = StateGraph(RequirementState)
    graph.add_node("intake", intake_node)
    graph.add_edge(START, "intake")
    graph.add_edge("intake", END)
    return graph.compile()

workflow_graph = build_graph()
