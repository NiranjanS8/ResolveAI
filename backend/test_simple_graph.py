import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from typing import TypedDict
from langgraph.graph import StateGraph, END

class SimpleState(TypedDict):
    value: str

def node1(state: SimpleState) -> SimpleState:
    return {"value": state["value"] + " -> node1"}

def node2(state: SimpleState) -> SimpleState:
    return {"value": state["value"] + " -> node2"}

async def test():
    workflow = StateGraph(SimpleState)
    workflow.add_node("node1", node1)
    workflow.add_node("node2", node2)
    workflow.set_entry_point("node1")
    workflow.add_edge("node1", "node2")
    workflow.add_edge("node2", END)
    
    graph = workflow.compile()
    
    result = await graph.ainvoke({"value": "start"})
    print(f"Result: {result}")

if __name__ == "__main__":
    asyncio.run(test())