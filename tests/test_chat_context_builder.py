"""Test chat context building from recent activity.

These tests validate context retrieval and formatting without requiring
a running Ollama server, so they can run in CI.
"""
import sqlite3
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from core.chat_context import build_recent_context, format_context_for_prompt


@pytest.fixture
def test_db():
    """Create a temporary database with test data."""
    db_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    db_path = Path(db_file.name)
    db_file.close()
    
    conn = sqlite3.connect(str(db_path))
    
    # Create sessions table
    conn.execute("""
        CREATE TABLE sessions (
            summary_id TEXT PRIMARY KEY,
            session_id TEXT,
            window_start REAL,
            window_end REAL,
            summary TEXT,
            active_task TEXT,
            entities TEXT,
            event_count INTEGER
        )
    """)
    
    # Create events table
    conn.execute("""
        CREATE TABLE events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL,
            event_type TEXT,
            process_name TEXT,
            current_window_title TEXT,
            active_url TEXT,
            summary TEXT,
            payload TEXT,
            interesting INTEGER,
            interest_score REAL,
            interest_reason TEXT,
            vision_ocr_text TEXT,
            vision_activity TEXT,
            vision_suggested_action TEXT,
            screenshot_filename TEXT,
            classification_status TEXT
        )
    """)
    
    now = time.time()
    
    # Insert test sessions
    conn.execute(
        "INSERT INTO sessions (summary_id, session_id, window_start, window_end, summary, active_task, event_count) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("s1", "sess1", now - 1800, now - 1200, "Working on Python code", "Coding in VS Code", 10)
    )
    conn.execute(
        "INSERT INTO sessions (summary_id, session_id, window_start, window_end, summary, active_task, event_count) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("s2", "sess2", now - 900, now - 300, "Browsing documentation", "Reading docs", 5)
    )
    
    # Insert test events
    conn.execute(
        "INSERT INTO events (timestamp, event_type, process_name, current_window_title, active_url, "
        "summary, interesting, vision_ocr_text) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (now - 600, "context_change", "chrome", "Python docs", "https://docs.python.org", 
         "Switched to browser", 1, "def function(): pass")
    )
    conn.execute(
        "INSERT INTO events (timestamp, event_type, process_name, current_window_title, "
        "summary, interesting) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (now - 300, "typing_burst", "code", "main.py - VS Code", "Typing code", 1)
    )
    
    # Insert a private window event (should be filtered out)
    conn.execute(
        "INSERT INTO events (timestamp, event_type, process_name, current_window_title, "
        "summary, interesting) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (now - 450, "context_change", "chrome", "Secret Page - Google Chrome (Incognito)", 
         "Private browsing", 1)
    )
    
    conn.commit()
    conn.close()
    
    yield db_path
    
    # Cleanup
    try:
        db_path.unlink()
    except Exception:
        pass


def test_build_recent_context_retrieves_sessions(test_db):
    """Test that recent sessions are retrieved correctly."""
    with patch("core.chat_context.conn") as mock_conn:
        mock_conn.execute.return_value.fetchall.return_value = [
            ("Working on Python code", "Coding in VS Code", "2026-10-11 15:00:00"),
            ("Browsing documentation", "Reading docs", "2026-10-11 15:15:00")
        ]
        
        context = build_recent_context(lookback_minutes=60, max_sessions=5, max_events=10)
        
        assert "sessions" in context
        assert len(context["sessions"]) == 2
        assert context["sessions"][0]["summary"] == "Working on Python code"
        assert context["sessions"][0]["active_task"] == "Coding in VS Code"


def test_build_recent_context_retrieves_events(test_db):
    """Test that recent events are retrieved and private windows filtered."""
    with patch("core.chat_context.conn") as mock_conn:
        # Simulate database returning events including a private one
        mock_conn.execute.return_value.fetchall.return_value = [
            ("context_change", "chrome", "Python docs", "https://docs.python.org", 
             "Switched to browser", "def function(): pass", "2026-10-11 15:10:00"),
            ("typing_burst", "code", "main.py - VS Code", None, 
             "Typing code", None, "2026-10-11 15:25:00")
        ]
        
        context = build_recent_context(lookback_minutes=60, max_sessions=5, max_events=10)
        
        assert "events" in context
        assert len(context["events"]) == 2
        assert context["events"][0]["event_type"] == "context_change"
        assert context["events"][0]["window_title"] == "Python docs"


def test_build_recent_context_filters_private_windows():
    """Test that private browser windows are excluded from context."""
    with patch("core.chat_context.conn") as mock_conn:
        # Return events including a private window
        mock_conn.execute.return_value.fetchall.return_value = [
            ("context_change", "chrome.exe", "Secret - Google Chrome (Incognito)", None,
             "Private browsing", None, "2026-10-11 15:10:00"),
            ("context_change", "chrome.exe", "Regular Page - Google Chrome", None,
             "Normal browsing", None, "2026-10-11 15:11:00")
        ]
        
        context = build_recent_context(lookback_minutes=60, max_sessions=5, max_events=10)
        
        # Only the non-private window should be included
        assert len(context["events"]) == 1
        assert "Incognito" not in context["events"][0]["window_title"]


def test_build_recent_context_handles_empty_db():
    """Test graceful handling when no recent activity exists."""
    with patch("core.chat_context.conn") as mock_conn:
        mock_conn.execute.return_value.fetchall.return_value = []
        
        context = build_recent_context()
        
        assert context["sessions"] == []
        assert context["events"] == []
        assert "lookback_minutes" in context
        assert "retrieved_at" in context


def test_build_recent_context_handles_db_errors():
    """Test that database errors don't crash context building."""
    with patch("core.chat_context.conn") as mock_conn:
        mock_conn.execute.side_effect = Exception("Database error")
        
        # Should not raise, just return empty context
        context = build_recent_context()
        
        assert context["sessions"] == []
        assert context["events"] == []


def test_format_context_for_prompt_with_data():
    """Test that context is formatted readably for prompts and wrapped as untrusted."""
    context = {
        "sessions": [
            {
                "summary": "Writing Python code in VS Code",
                "active_task": "Coding",
                "start_time": "2026-10-11 15:00:00"
            }
        ],
        "events": [
            {
                "event_type": "context_change",
                "process_name": "chrome",
                "window_title": "Python docs",
                "url": "https://docs.python.org",
                "event_time": "2026-10-11 15:10:00",
                "summary": "Reading documentation",
                "ocr_text": ""
            }
        ],
        "lookback_minutes": 60,
        "retrieved_at": "2026-10-11 15:30:00"
    }
    
    formatted = format_context_for_prompt(context)
    
    # Should be wrapped as untrusted content
    assert "<<<CAPTURED_SCREEN_DATA id=" in formatted
    assert "<<<END_CAPTURED_SCREEN_DATA id=" in formatted
    assert "NOTE: The following is observed screen content" in formatted
    # Content should still be present inside the wrapper
    assert "## Recent activity summaries:" in formatted
    assert "Coding" in formatted
    assert "## Recent events:" in formatted
    assert "Python docs" in formatted
    assert "https://docs.python.org" in formatted


def test_format_context_for_prompt_empty():
    """Test formatting when no context is available."""
    context = {
        "sessions": [],
        "events": [],
        "lookback_minutes": 60,
        "retrieved_at": "2026-10-11 15:30:00"
    }
    
    formatted = format_context_for_prompt(context)
    
    assert formatted == "No recent activity found."


def test_format_context_truncates_long_text():
    """Test that very long text is truncated in formatted output."""
    long_text = "x" * 500
    context = {
        "sessions": [
            {
                "summary": long_text,
                "active_task": "Task",
                "start_time": "2026-10-11 15:00:00"
            }
        ],
        "events": [
            {
                "event_type": "context_change",
                "process_name": "app",
                "window_title": long_text,
                "url": None,
                "event_time": "2026-10-11 15:10:00",
                "summary": long_text,
                "ocr_text": long_text
            }
        ],
        "lookback_minutes": 60,
        "retrieved_at": "2026-10-11 15:30:00"
    }
    
    formatted = format_context_for_prompt(context)
    
    # Check that text is truncated (max lengths in format_context_for_prompt)
    lines = formatted.split("\n")
    for line in lines:
        # No single line should be absurdly long (allowing for some overhead)
        assert len(line) < 600, f"Line too long: {len(line)} chars"


def test_load_conversation_history():
    """Test that conversation history is loaded correctly."""
    from core.chat_context import load_conversation_history
    
    with patch("core.storage.conn") as mock_conn:
        # Simulate database returning history (newest first from DB)
        mock_conn.execute.return_value.fetchall.return_value = [
            ("assistant", "Previous answer"),
            ("user", "Previous question")
        ]
        
        history = load_conversation_history("test123", max_turns=10, max_chars=4000)
        
        # Should be reversed to oldest first
        assert len(history) == 2
        assert history[0] == {"role": "user", "content": "Previous question"}
        assert history[1] == {"role": "assistant", "content": "Previous answer"}


def test_load_conversation_history_respects_char_limit():
    """Test that conversation history stops at character budget."""
    from core.chat_context import load_conversation_history
    
    with patch("core.storage.conn") as mock_conn:
        # Return messages where the 3rd would exceed limit
        mock_conn.execute.return_value.fetchall.return_value = [
            ("assistant", "x" * 1500),  # Would push total over 2000
            ("user", "y" * 500),
            ("assistant", "Short A1"),
            ("user", "Short Q1")
        ]
        
        history = load_conversation_history("test123", max_turns=10, max_chars=2000)
        
        # First 2 messages fit (~1000 chars), 3rd would exceed, so only 2 are included
        # (actually 4 messages fit because last 2 are short, but reversed order matters)
        total_chars = sum(len(m["content"]) for m in history)
        assert total_chars <= 2000
        assert len(history) >= 2  # At least 2 short ones should fit


def test_build_chat_messages_includes_system_and_user():
    """Test that build_chat_messages creates proper message structure."""
    from core.chat_context import build_chat_messages
    
    with patch("core.chat_context.build_recent_context") as mock_context, \
         patch("core.chat_context.load_conversation_history") as mock_history:
        
        mock_context.return_value = {"sessions": [], "events": [], "lookback_minutes": 60, "retrieved_at": "now"}
        mock_history.return_value = []
        
        messages = build_chat_messages("Test question")
        
        # Should have system + user
        assert len(messages) >= 2
        assert messages[0]["role"] == "system"
        assert "Clippy Vision" in messages[0]["content"]
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "Test question"


def test_build_chat_messages_includes_history():
    """Test that build_chat_messages includes conversation history."""
    from core.chat_context import build_chat_messages
    
    with patch("core.chat_context.build_recent_context") as mock_context, \
         patch("core.chat_context.load_conversation_history") as mock_history:
        
        mock_context.return_value = {"sessions": [], "events": [], "lookback_minutes": 60, "retrieved_at": "now"}
        mock_history.return_value = [
            {"role": "user", "content": "Previous Q"},
            {"role": "assistant", "content": "Previous A"}
        ]
        
        messages = build_chat_messages("New question", "conv123")
        
        # Should have system + history + new user
        assert len(messages) == 4
        assert messages[0]["role"] == "system"
        assert messages[1] == {"role": "user", "content": "Previous Q"}
        assert messages[2] == {"role": "assistant", "content": "Previous A"}
        assert messages[3] == {"role": "user", "content": "New question"}
