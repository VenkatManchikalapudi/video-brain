"""Session management for conversation history.

Manages per-session conversation context for multi-turn interactions.
"""

import logging
from typing import Dict, List, Optional

from models import ConversationMessage, AIResponse

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages conversation sessions and history.
    
    For production, consider replacing _SESSIONS with a persistent
    database (PostgreSQL, MongoDB, Redis, etc.).
    """
    
    def __init__(self):
        """Initialize session manager."""
        # In-memory store: session_id -> list of messages
        self._sessions: Dict[str, List[ConversationMessage]] = {}
    
    def get_or_create_session(self, session_id: str) -> List[ConversationMessage]:
        """Get or create a session."""
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        return self._sessions[session_id]
    
    def add_user_message(self, session_id: str, message: str) -> None:
        """Add a user message to the session."""
        history = self.get_or_create_session(session_id)
        msg = ConversationMessage(role="user", text=message)
        history.append(msg)
        logger.debug(f"Added user message to session {session_id}")
    
    def add_assistant_message(self, session_id: str, response: AIResponse) -> None:
        """Add an AI response to the session."""
        history = self.get_or_create_session(session_id)
        msg = ConversationMessage(role="assistant", text=response.text)
        history.append(msg)
        logger.debug(f"Added assistant message to session {session_id}")
    
    def get_history(self, session_id: str) -> List[ConversationMessage]:
        """Get conversation history for a session."""
        return self.get_or_create_session(session_id)
    
    def clear_session(self, session_id: str) -> None:
        """Clear all history for a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.debug(f"Cleared session {session_id}")
    
    def get_recent_history(
        self,
        session_id: str,
        max_messages: int = 10
    ) -> List[ConversationMessage]:
        """Get recent messages from a session (useful for context window limits).
        
        Args:
            session_id: Session identifier
            max_messages: Maximum number of messages to return
            
        Returns:
            List of recent conversation messages
        """
        history = self.get_or_create_session(session_id)
        return history[-max_messages:] if history else []


# Singleton instance
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get or create the singleton session manager."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
