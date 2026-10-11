"""Build conversation context from recent captured activity for in-app chat.

Retrieves recent sessions and events to provide the chat agent with context
about what the user has been doing. Respects privacy settings by excluding
events from private windows.
"""
from __future__ import annotations

import time
from typing import Any

from agent.untrusted_wrapper import wrap_untrusted_content
from core.private_windows import root_name_is_private
from core.storage import conn


def build_recent_context(lookback_minutes: int = 60, max_sessions: int = 5, max_events: int = 10) -> dict[str, Any]:
    """Build context from recent activity for chat prompts.
    
    Args:
        lookback_minutes: How far back to look for activity
        max_sessions: Maximum session summaries to include
        max_events: Maximum recent events to include
    
    Returns:
        Dict with 'sessions' and 'events' lists, plus metadata
    """
    now = time.time()
    cutoff = now - (lookback_minutes * 60)
    
    # Get recent session summaries
    sessions = []
    try:
        rows = conn.execute(
            """SELECT summary, active_task, 
                      datetime(window_start, 'unixepoch', 'localtime') as start_time
               FROM sessions 
               WHERE window_start >= ? 
                 AND summary IS NOT NULL 
                 AND summary != ''
               ORDER BY window_start DESC 
               LIMIT ?""",
            (cutoff, max_sessions)
        ).fetchall()
        
        for row in rows:
            sessions.append({
                "summary": row[0],
                "active_task": row[1],
                "start_time": row[2]
            })
    except Exception as e:
        print(f"[chat_context] session retrieval failed: {e}")
    
    # Get recent events, excluding private windows
    events = []
    try:
        rows = conn.execute(
            """SELECT event_type, process_name, current_window_title, 
                      active_url, summary, vision_ocr_text,
                      datetime(timestamp, 'unixepoch', 'localtime') as event_time
               FROM events 
               WHERE timestamp >= ?
                 AND (interesting = 1 OR event_type IN ('paste', 'clipboard_change', 'context_change'))
               ORDER BY timestamp DESC 
               LIMIT ?""",
            (cutoff, max_events * 2)  # Fetch extra to account for filtering
        ).fetchall()
        
        for row in rows:
            if len(events) >= max_events:
                break
            
            process_name = row[1] or ""
            window_title = row[2] or ""
            
            # Skip events from private windows
            if root_name_is_private(window_title, process_name):
                continue
            
            events.append({
                "event_type": row[0],
                "process_name": process_name,
                "window_title": window_title,
                "url": row[3],
                "summary": row[4],
                "ocr_text": row[5],
                "event_time": row[6]
            })
    except Exception as e:
        print(f"[chat_context] event retrieval failed: {e}")
    
    return {
        "sessions": sessions,
        "events": events,
        "lookback_minutes": lookback_minutes,
        "retrieved_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))
    }


def format_context_for_prompt(context: dict[str, Any]) -> str:
    """Format context dict into a readable system message section.
    
    All captured screen data (window titles, URLs, OCR text, summaries) is
    wrapped as untrusted content to prevent prompt injection attacks.
    
    Args:
        context: Output from build_recent_context()
    
    Returns:
        Formatted string for inclusion in chat prompts, wrapped as untrusted
    """
    lines = []
    
    if context["sessions"]:
        lines.append("## Recent activity summaries:")
        for session in context["sessions"]:
            task = session.get("active_task", "").strip()
            summary = session.get("summary", "").strip()
            start_time = session.get("start_time", "")
            
            if task:
                lines.append(f"- [{start_time}] {task}")
            if summary and summary != task:
                lines.append(f"  {summary[:300]}")
    
    if context["events"]:
        lines.append("\n## Recent events:")
        for event in context["events"]:
            event_type = event.get("event_type", "")
            process = event.get("process_name", "")
            title = event.get("window_title", "")
            url = event.get("url", "")
            event_time = event.get("event_time", "")
            
            parts = [f"[{event_time}]"]
            if process:
                parts.append(process)
            if title:
                parts.append(f'"{title[:100]}"')
            if url:
                parts.append(f"({url})")
            
            lines.append(f"- {' '.join(parts)}")
            
            # Include summary or OCR if available
            summary = event.get("summary", "").strip()
            ocr = event.get("ocr_text", "").strip()
            if summary:
                lines.append(f"  {summary[:200]}")
            elif ocr and len(ocr) > 20:
                lines.append(f"  Screen text: {ocr[:150]}")
    
    if not lines:
        return "No recent activity found."
    
    # Wrap all screen-captured content as untrusted to prevent prompt injection
    return wrap_untrusted_content("\n".join(lines))


def load_conversation_history(conversation_id: str, max_turns: int = 10, max_chars: int = 4000) -> list[dict[str, str]]:
    """Load recent conversation history for multi-turn context.
    
    Args:
        conversation_id: Conversation to load history for
        max_turns: Maximum number of turns (user+assistant pairs) to include
        max_chars: Maximum total characters across all messages
    
    Returns:
        List of message dicts with 'role' and 'content' keys, oldest first
    """
    from core.storage import conn
    
    try:
        rows = conn.execute(
            """SELECT role, content FROM conversations 
               WHERE conversation_id = ? 
               ORDER BY timestamp DESC 
               LIMIT ?""",
            (conversation_id, max_turns * 2)
        ).fetchall()
        
        # Reverse to get oldest first
        messages = []
        total_chars = 0
        for row in reversed(rows):
            role = row[0]
            content = row[1] or ""
            
            # Stop if we exceed character budget
            if total_chars + len(content) > max_chars:
                break
            
            messages.append({"role": role, "content": content})
            total_chars += len(content)
        
        return messages
    except Exception as e:
        print(f"[chat_context] conversation history retrieval failed: {e}")
        return []


def build_chat_messages(user_message: str, conversation_id: str | None = None) -> list[dict[str, str]]:
    """Build complete message list for chat API including context and history.
    
    Args:
        user_message: The new user message
        conversation_id: Optional conversation ID for multi-turn history
    
    Returns:
        List of message dicts ready for Ollama API
    """
    # Build activity context
    context = build_recent_context(lookback_minutes=60, max_sessions=5, max_events=10)
    context_text = format_context_for_prompt(context)
    
    # System prompt with context
    system_message = (
        "You are Clippy Vision's assistant. You have access to the user's recent "
        "captured activity (screen text, window titles, apps used, and summaries). "
        "Answer questions about their activity concisely and helpfully.\n\n"
        f"{context_text}"
    )
    
    messages = [{"role": "system", "content": system_message}]
    
    # Add conversation history if available
    if conversation_id:
        history = load_conversation_history(conversation_id, max_turns=10, max_chars=4000)
        messages.extend(history)
    
    # Add new user message
    messages.append({"role": "user", "content": user_message})
    
    return messages
