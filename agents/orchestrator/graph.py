"""Unified human-gated delivery orchestration over approved phase artifacts.

Invoked afresh from immutable persisted snapshots. Does NOT call Ollama or
publish externally. Approval decisions are persisted separately by FastAPI.
"""
from langgraph.graph import START, END, StateGraph
from agents.orchestrator.nodes import (
    intake_node, research_agent, story_agent, design_agent, design_gate,
    planning_agent, planning_gate,
)
from agents.orchestrator.state import RequirementState


def build_graph():
    graph = StateGraph(RequirementState)
    for name, node in (
        ('intake', intake_node), ('research', research_agent),
        ('stories', story_agent), ('design', design_agent),
        ('design_approval', design_gate), ('planning', planning_agent),
        ('planning_approval', planning_gate),
    ):
        graph.add_node(name, node)
    graph.add_edge(START, 'intake')
    graph.add_edge('intake', 'research')
    graph.add_edge('research', 'stories')
    graph.add_edge('stories', 'design')
    graph.add_edge('design', 'design_approval')
    graph.add_conditional_edges('design_approval',
                                lambda s: 'planning' if s.get('design_approval') == 'approved' else END,
                                {'planning': 'planning', END: END})
    graph.add_edge('planning', 'planning_approval')
    graph.add_edge('planning_approval', END)
    return graph.compile()


workflow_graph = build_graph()
