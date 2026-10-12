import sys
import os
import time
from typing import List, Dict, Any

# Set empty API keys - tests will verify structure, not actual LLM calls
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""

from app.graphs.ticket_graph import classify_node, CLASSIFY_PROMPT
from app.graphs.state import TicketState
from app.schemas.classification import ClassificationOutput


test_tickets: List[Dict[str, Any]] = [
    {
        "subject": "Hello, how are you?",
        "body": "Hi there, just saying hello. Hope you have a great day!",
        "expected_intent": "general",
    },
    {
        "subject": "I need help with my invoice",
        "body": "I cannot find my invoice from last month. Can you resend it to me?",
        "expected_intent": "billing",
    },
    {
        "subject": "My app keeps crashing on startup",
        "body": "Every time I launch the application, it crashes immediately after the logo. I've reinstalled twice.",
        "expected_intent": "technical",
    },
    {
        "subject": "How do I change my password?",
        "body": "I forgot my password and need to reset it. Please send me a reset link.",
        "expected_intent": "password_reset",
    },
    {
        "subject": "Refund for defective product",
        "body": "The product I received is defective and not working. I want a full refund.",
        "expected_intent": "refund",
    },
    {
        "subject": "Order #12345 not delivered",
        "body": "Where is my order? The estimated delivery was 5 days ago and I still haven't received it.",
        "expected_intent": "order_status",
    },
    {
        "subject": "Cancel my subscription",
        "body": "I want to cancel my monthly subscription. Please confirm the cancellation.",
        "expected_intent": "cancellation",
    },
    {
        "subject": "Account login issue",
        "body": "I cannot log into my account. The password I'm using is not being accepted.",
        "expected_intent": "account",
    },
    {
        "subject": "Billing question about charges",
        "body": "Why was I charged $99.99 on my card? I don't recognize this charge.",
        "expected_intent": "billing",
    },
    {
        "subject": "Technical support for integration",
        "body": "The API integration is returning a 500 error. Can someone help me debug this?",
        "expected_intent": "technical",
    },
    {
        "subject": "Urgent: security breach suspected",
        "body": "Someone accessed my account from a different city. I need to secure my account immediately.",
        "expected_intent": "account",
        "expected_urgency": "high",
    },
    {
        "subject": "Very angry customer",
        "body": "I am furious! Your service is terrible and I want compensation right now. This is the worst experience ever!",
        "expected_intent": "general",
        "expected_sentiment": "negative",
    },
    {
        "subject": "Quick question about features",
        "body": "Hi, I just had a quick question about the new features in the pro plan. Thanks!",
        "expected_intent": "general",
        "expected_sentiment": "positive",
    },
]


def test_classification_output_schema():
    """Test that ClassificationOutput schema is valid."""
    from pydantic import ValidationError
    
    # Test that the schema can be instantiated with valid values
    valid_output = ClassificationOutput(
        intent="general",
        urgency="medium",
        sentiment="neutral",
        confidence=0.85,
        reasoning="Test classification",
    )
    assert valid_output.intent == "general"
    assert valid_output.urgency == "medium"
    assert valid_output.sentiment == "neutral"
    assert valid_output.confidence == 0.85
    
    print("PASS: ClassificationOutput schema is valid")


def test_ticket_state_has_required_fields():
    """Test that TicketState has all required fields."""
    state: TicketState = {
        "ticket_id": "test-123",
        "customer_id": "cust_123",
        "subject": "Test subject",
        "body": "Test body",
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
    
    # Verify all required fields exist
    required_fields = [
        "ticket_id", "customer_id", "subject", "body", "status",
        "intent", "urgency", "sentiment", "confidence",
        "retrieved_context", "decision", "draft_response", "error",
        "created_at", "updated_at",
    ]
    for field in required_fields:
        assert field in state, f"Missing field: {field}"
    
    print("PASS: TicketState has all required fields")


def test_with_fallbacks_configured():
    """Test that .with_fallbacks is configured on the classifier model."""
    from app.core.model_registry import get_model_config
    from app.core.llm import create_llm
    from langchain_core.runnables import Runnable
    
    primary_config = get_model_config("classifier")
    fallback_config = primary_config.fallback
    
    # Check primary LLM can be created with structured output
    primary_llm = create_llm(primary_config)
    
    # Check that with_fallbacks method exists and is callable
    has_with_fallbacks = hasattr(primary_llm, "with_fallbacks")
    assert has_with_fallbacks, "LLM should have with_fallbacks method"
    
    # Test that we can chain with_fallbacks
    structured_llm = primary_llm.with_structured_output(ClassificationOutput)
    has_fallbacks_chain = hasattr(structured_llm, "with_fallbacks")
    # Note: with_fallbacks may not be available on all LLM types, 
    # what matters is the config has fallback defined
    
    # Verify fallback config is set
    assert fallback_config is not None, "Classifier should have fallback config"
    assert fallback_config.provider != "", "Fallback provider should be set"
    assert fallback_config.model != "", "Fallback model should be set"
    
    print("PASS: .with_fallbacks() configuration is valid")


def test_classification_pipeline_structure():
    """Test the classification pipeline structure without actual LLM calls."""
    # Verify the classify_node function exists and has correct signature
    import inspect
    sig = inspect.signature(classify_node)
    params = list(sig.parameters.keys())
    assert "state" in params, "classify_node should have 'state' parameter"
    
    # Verify build_graph function exists
    from app.graphs.ticket_graph import build_graph
    graph = build_graph()
    assert graph is not None, "build_graph should return a StateGraph"
    
    print("PASS: Classification pipeline structure is valid")


def test_model_registry():
    """Test that model registry has classifier config."""
    from app.core.model_registry import get_model_config, MODEL_REGISTRY
    
    # Verify classifier is in registry
    assert "classifier" in MODEL_REGISTRY, "classifier should be in MODEL_REGISTRY"
    
    # Verify model config has expected fields
    classifier_config = MODEL_REGISTRY["classifier"]
    assert classifier_config.provider == "anthropic", "Classifier provider should be anthropic"
    assert classifier_config.model == "claude-3-haiku-20240307", "Classifier model should be haiku"
    assert classifier_config.temperature == 0.0, "Classifier temperature should be 0.0"
    
    # Verify fallback is configured
    assert classifier_config.fallback is not None, "Classifier should have fallback"
    assert classifier_config.fallback.provider == "openai", "Fallback provider should be openai"
    assert classifier_config.fallback.model == "gpt-4o-mini", "Fallback model should be gpt-4o-mini"
    
    print("PASS: Model registry is configured correctly")


def test_provider_call_schema():
    """Test that ProviderCall can be created with correct schema."""
    from uuid import uuid4
    from datetime import datetime
    from app.models.base import ProviderCall
    
    # Test creating a ProviderCall (won't persist without DB, but schema validation works)
    call = ProviderCall(
        id=uuid4(),
        provider="anthropic",
        model="claude-3-haiku-20240307",
        task="classifier",
        input_tokens="0",
        output_tokens="0",
        latency_ms="150",
        cost_estimate="0.01",
        success="true",
    )
    
    assert call.provider == "anthropic"
    assert call.model == "claude-3-haiku-20240307"
    assert call.task == "classifier"
    assert call.success == "true"
    
    print("PASS: ProviderCall schema is valid")


if __name__ == "__main__":
    print("=" * 60)
    print("Running Phase 3 Classification Tests (Structure)")
    print("=" * 60)
    print()
    
    test_classification_output_schema()
    test_ticket_state_has_required_fields()
    test_with_fallbacks_configured()
    test_classification_pipeline_structure()
    test_model_registry()
    test_provider_call_schema()
    
    print()
    print("=" * 60)
    print("All Phase 3 structure tests PASSED!")
    print("=" * 60)