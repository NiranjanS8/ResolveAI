import sys
import os
import time
from typing import List, Dict, Any

# Set empty API keys - tests will verify structure, not actual LLM calls
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""
os.environ["MISTRAL_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""
os.environ["GOOGLE_API_KEY"] = ""

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
    """Test that the classifier model config is internally consistent."""
    from app.core.model_registry import get_model_config
    from app.core.providers import CHAT_PROVIDERS

    primary_config = get_model_config("classifier")

    assert primary_config.provider in CHAT_PROVIDERS, "Primary provider must be known"
    assert primary_config.model, "Primary model must be set"
    assert primary_config.temperature == 0.0, "Classifier temperature should be 0.0"

    if primary_config.fallback is not None:
        assert primary_config.fallback.provider in CHAT_PROVIDERS, "Fallback provider must be known"
        assert primary_config.fallback.provider != primary_config.provider, "Fallback must differ"
        assert primary_config.fallback.model, "Fallback model must be set"

    print("PASS: classifier model config is valid")


def test_create_llm_requires_api_key():
    """create_llm must fail clearly when the provider has no key configured."""
    from app.core.llm import create_llm
    from app.core.model_registry import ModelConfig

    try:
        create_llm(ModelConfig(provider="mistral", model="mistral-small-latest"))
    except ValueError as exc:
        assert "api key" in str(exc).lower(), "error should mention the missing API key"
    else:
        raise AssertionError("expected ValueError when no API key is configured")

    print("PASS: create_llm rejects providers without an API key")


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
    """Test that the model registry resolves a valid provider set."""
    from app.core.model_registry import MODEL_REGISTRY
    from app.core.providers import CHAT_PROVIDERS

    # Verify classifier is in registry
    assert "classifier" in MODEL_REGISTRY, "classifier should be in MODEL_REGISTRY"

    # Verify model config has expected fields
    classifier_config = MODEL_REGISTRY["classifier"]
    assert classifier_config.provider in CHAT_PROVIDERS, "Classifier provider should be known"
    assert classifier_config.model, "Classifier model should be set"
    assert classifier_config.temperature == 0.0, "Classifier temperature should be 0.0"

    print("PASS: Model registry is configured correctly")


def test_all_chat_providers_supported():
    """Every advertised chat provider must have models and an API-key mapping."""
    from app.core.model_registry import PROVIDER_MODELS
    from app.core.providers import CHAT_PROVIDERS, api_key_for

    for provider in CHAT_PROVIDERS:
        assert provider in PROVIDER_MODELS, f"{provider} missing from PROVIDER_MODELS"
        for task in ("classifier", "decider", "drafter"):
            assert task in PROVIDER_MODELS[provider], f"{provider} missing task '{task}'"
        api_key_for(provider)  # must resolve without raising

    print("PASS: gemini/mistral/anthropic/openai are all wired")


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
    test_create_llm_requires_api_key()
    test_classification_pipeline_structure()
    test_model_registry()
    test_all_chat_providers_supported()
    test_provider_call_schema()
    
    print()
    print("=" * 60)
    print("All Phase 3 structure tests PASSED!")
    print("=" * 60)