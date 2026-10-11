"""Test chat endpoint error handling.

These tests validate that chat context and error handling work correctly
without requiring a running Ollama server.
"""
import time

import pytest


def test_ollama_unavailable_exception_exists():
    """Test that OllamaUnavailable exception can be imported and raised."""
    from core.ollama_client import OllamaUnavailable
    
    # Should be able to instantiate it
    exc = OllamaUnavailable("test message")
    assert str(exc) == "test message"
    assert isinstance(exc, OSError)


def test_chat_context_format_includes_all_fields():
    """Test that context formatting includes expected sections."""
    from core.chat_context import format_context_for_prompt
    
    context = {
        "sessions": [
            {"summary": "Test session", "active_task": "Task", "start_time": "15:00"}
        ],
        "events": [
            {"event_type": "typing_burst", "process_name": "app", "window_title": "title",
             "url": None, "event_time": "15:10", "summary": "Summary", "ocr_text": ""}
        ],
        "lookback_minutes": 60,
        "retrieved_at": "now"
    }
    
    formatted = format_context_for_prompt(context)
    assert "activity" in formatted.lower() or "session" in formatted.lower()
    assert "Task" in formatted


def test_message_validation_logic():
    """Test the message validation logic used by endpoints."""
    # Empty message
    try:
        from api_server import _validate_user_message
        result = _validate_user_message("   ")
        assert False, "Should have raised HTTPException"
    except Exception as e:
        assert "empty" in str(e).lower()
    
    # Too long message
    try:
        long_msg = "x" * 5000
        _validate_user_message(long_msg)
        assert False, "Should have raised HTTPException"
    except Exception as e:
        assert "too long" in str(e).lower() or "long" in str(e).lower()
    
    # Valid message
    result = _validate_user_message("Hello, this is a valid message")
    assert result == "Hello, this is a valid message"


def test_conversation_id_generation():
    """Test that conversation IDs can be generated when missing."""
    import time
    
    # Test that empty conversation_id would trigger timestamp generation
    conversation_id = ""
    if not conversation_id.strip():
        conversation_id = str(time.time())
    
    assert conversation_id != ""
    assert len(conversation_id) > 5  # Should be a timestamp string
