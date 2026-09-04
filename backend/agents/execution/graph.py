"""LangGraph StateGraph wiring for the GROCER v2 execution agent (spec section 19).

Graph topology:
    START -> validate -> pre_check -> execute -> verify -> finalize | recover -> END

Conditional routing:
    After validate:   error set  -> END (fail fast)
    After pre_check:  not passed -> recover -> END
    After execute:    error set  -> recover -> END
    After verify:     not verified -> recover -> END
    Otherwise:        finalize -> END
"""
from __future__ import annotations

from langgraph.graph import StateGraph, END

from backend.agents.execution.state import AgentState
from backend.agents.execution.nodes import (
    node_validate,
    node_pre_check,
    node_execute,
    node_verify,
    node_finalize,
    node_recover,
)


# ---------------------------------------------------------------------------
# Routing functions
# ---------------------------------------------------------------------------

def _route_after_validate(state: AgentState) -> str:
    """Fail fast if validate produced an error."""
    if state.get("error"):
        return "end_failed"
    return "pre_check"


def _route_after_pre_check(state: AgentState) -> str:
    """Divert to recover if world state has changed."""
    if not state.get("pre_check_passed", True):
        return "recover"
    return "execute"


def _route_after_execute(state: AgentState) -> str:
    """Divert to recover on execution error."""
    if state.get("execution_error"):
        return "recover"
    return "verify"


def _route_after_verify(state: AgentState) -> str:
    """Divert to recover if verification failed."""
    if not state.get("verified", False):
        return "recover"
    return "finalize"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_execution_graph() -> StateGraph:
    """Build and return the compiled LangGraph execution graph."""
    builder = StateGraph(AgentState)

    # Add nodes
    builder.add_node("validate",  node_validate)
    builder.add_node("pre_check", node_pre_check)
    builder.add_node("execute",   node_execute)
    builder.add_node("verify",    node_verify)
    builder.add_node("finalize",  node_finalize)
    builder.add_node("recover",   node_recover)

    # Entry
    builder.set_entry_point("validate")

    # Conditional edges
    builder.add_conditional_edges(
        "validate",
        _route_after_validate,
        {
            "pre_check":   "pre_check",
            "end_failed":  END,
        },
    )
    builder.add_conditional_edges(
        "pre_check",
        _route_after_pre_check,
        {
            "execute": "execute",
            "recover": "recover",
        },
    )
    builder.add_conditional_edges(
        "execute",
        _route_after_execute,
        {
            "verify":  "verify",
            "recover": "recover",
        },
    )
    builder.add_conditional_edges(
        "verify",
        _route_after_verify,
        {
            "finalize": "finalize",
            "recover":  "recover",
        },
    )

    # Terminal edges
    builder.add_edge("finalize", END)
    builder.add_edge("recover",  END)

    return builder.compile()


# Module-level compiled graph (singleton; import and call .ainvoke())
execution_graph = build_execution_graph()
