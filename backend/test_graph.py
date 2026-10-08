import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import asyncio
from app.graphs import get_compiled_graph
from app.graphs.state import TicketState

def test_graph():
    graph = get_compiled_graph()
    initial_state: TicketState = {
        "ticket_id": "test-123",
        "customer_id": "cust_123",
        "subject": "Test ticket",
        "body": "This is a test ticket body",
        "status": "new",
        "intent": None,
        "urgency": None,
        "sentiment": None,
        "confidence": None,
        "retrieved_context": None,
        "decision": None,
        "draft_response": None,
        "error": None,
        "created_at": "2026-10-08T12:00:00Z",
        "updated_at": "2026-10-08T12:00:00Z",
    }
    print("Running graph...")
    config = {"configurable": {"thread_id": "test-thread-123"}}
    result = graph.invoke(initial_state, config=config)
    print(f"Result: {result}")
    return result

if __name__ == "__main__":
    test_graph()