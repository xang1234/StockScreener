"""
API endpoints for the Financial Research Chatbot.

Provides:
- Conversation management (create, list, get, delete)
- Message handling with streaming responses
- Multi-agent research pipeline access
"""
import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, asc

from ...database import get_db
from ...models.chatbot import Conversation, Message
from ...schemas.chatbot import (
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    ConversationDetailResponse,
    ConversationListResponse,
    MessageCreate,
    MessageResponse,
)
from ...services.chatbot import AgentOrchestrator
from ...services.chatbot.research import DeepResearchOrchestrator
from ...config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== Conversation Management ====================

@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    request: Optional[ConversationCreate] = None,
    db: Session = Depends(get_db)
):
    """
    Create a new conversation.

    Returns a new conversation with a unique ID that can be used
    for subsequent message exchanges.
    """
    conversation_id = str(uuid.uuid4())
    title = request.title if request and request.title else "New Conversation"

    conversation = Conversation(
        conversation_id=conversation_id,
        title=title,
        is_active=True,
        message_count=0
    )

    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    logger.info(f"Created conversation: {conversation_id}")
    return conversation


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    limit: int = Query(20, ge=1, le=100, description="Number of conversations to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db)
):
    """
    List all conversations, sorted by most recent.
    """
    total = db.query(Conversation).filter(Conversation.is_active == True).count()

    conversations = (
        db.query(Conversation)
        .filter(Conversation.is_active == True)
        .order_by(desc(Conversation.updated_at))
        .offset(offset)
        .limit(limit)
        .all()
    )

    return ConversationListResponse(
        conversations=conversations,
        total=total
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db)
):
    """
    Get a conversation with its full message history.
    Uses joinedload to fetch conversation + messages in a single query (avoiding N+1).
    """
    conversation = (
        db.query(Conversation)
        .options(joinedload(Conversation.messages))
        .filter(Conversation.conversation_id == conversation_id)
        .first()
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Sort messages by created_at (joinedload doesn't preserve order)
    sorted_messages = sorted(conversation.messages, key=lambda m: m.created_at)

    return ConversationDetailResponse(
        id=conversation.id,
        conversation_id=conversation.conversation_id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        is_active=conversation.is_active,
        message_count=conversation.message_count,
        messages=sorted_messages
    )


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db)
):
    """
    Delete a conversation and all its messages.
    """
    conversation = (
        db.query(Conversation)
        .filter(Conversation.conversation_id == conversation_id)
        .first()
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Hard delete - cascade will remove associated messages
    db.delete(conversation)
    db.commit()

    logger.info(f"Deleted conversation: {conversation_id}")
    return {"status": "deleted", "conversation_id": conversation_id}


@router.patch("/conversations/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: str,
    updates: ConversationUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a conversation's title and/or folder.
    """
    conversation = (
        db.query(Conversation)
        .filter(Conversation.conversation_id == conversation_id)
        .first()
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Update title if provided
    if updates.title is not None:
        conversation.title = updates.title

    # Update folder_id (can be set to None to remove from folder)
    if 'folder_id' in updates.model_fields_set:
        conversation.folder_id = updates.folder_id

    db.commit()
    db.refresh(conversation)

    logger.info(f"Updated conversation: {conversation_id}")
    return conversation


# ==================== Message Handling ====================

@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    request: MessageCreate,
    db: Session = Depends(get_db)
):
    """
    Send a message and get a streaming response.

    The response is a Server-Sent Events (SSE) stream containing:
    - thinking: Agent thinking/planning updates
    - tool_call: Tool being called
    - tool_result: Tool execution result
    - content: Response content chunks
    - done: Completion signal
    - error: Error message (if any)

    Example usage:
    ```javascript
    const eventSource = new EventSource('/api/v1/chatbot/conversations/{id}/messages');
    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'content') {
            // Append to response
        }
    };
    ```
    """
    # Verify conversation exists
    conversation = (
        db.query(Conversation)
        .filter(Conversation.conversation_id == conversation_id)
        .first()
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    async def generate():
        """Generate SSE stream from orchestrator."""
        # Check if deep research mode is requested and enabled
        if request.research_mode and settings.deep_research_enabled:
            research_orchestrator = DeepResearchOrchestrator(db)
            try:
                # Get conversation history for context
                messages = (
                    db.query(Message)
                    .filter(Message.conversation_id == conversation_id)
                    .filter(Message.role.in_(["user", "assistant"]))
                    .order_by(Message.created_at.desc())
                    .limit(10)
                    .all()
                )
                history = [
                    {"role": msg.role, "content": msg.content}
                    for msg in reversed(messages)
                ]

                async for chunk in research_orchestrator.research(
                    conversation_id,
                    request.content,
                    history=history
                ):
                    yield f"data: {json.dumps(chunk)}\n\n"
            except Exception as e:
                logger.error(f"Error in research stream: {e}")
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
        else:
            # Standard tool agent flow
            orchestrator = AgentOrchestrator(db)
            try:
                async for chunk in orchestrator.process_message(
                    conversation_id,
                    request.content,
                    enabled_tools=request.enabled_tools
                ):
                    yield f"data: {json.dumps(chunk)}\n\n"
            except Exception as e:
                logger.error(f"Error in message stream: {e}")
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
            finally:
                await orchestrator.close()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@router.post("/conversations/{conversation_id}/messages/sync")
async def send_message_sync(
    conversation_id: str,
    request: MessageCreate,
    db: Session = Depends(get_db)
):
    """
    Send a message and get a non-streaming response.

    Use this endpoint when SSE is not supported or for simpler integrations.
    Returns the complete response after all processing is done.
    """
    # Verify conversation exists
    conversation = (
        db.query(Conversation)
        .filter(Conversation.conversation_id == conversation_id)
        .first()
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    orchestrator = AgentOrchestrator(db)

    try:
        result = await orchestrator.process_simple_query(conversation_id, request.content)
        return result
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await orchestrator.close()


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
async def get_messages(
    conversation_id: str,
    limit: int = Query(50, ge=1, le=200, description="Number of messages to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db)
):
    """
    Get message history for a conversation.
    """
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
        .offset(offset)
        .limit(limit)
        .all()
    )

    return messages


# ==================== Utility Endpoints ====================

@router.get("/tools")
async def get_available_tools(db: Session = Depends(get_db)):
    """
    Get a list of all available tools the chatbot can use.

    Useful for understanding what capabilities the chatbot has.
    """
    from ...services.chatbot.action_agent import ActionAgent
    action_agent = ActionAgent(db)
    tools = action_agent.get_available_tools()
    return {"tools": tools, "count": len(tools)}


@router.get("/health")
async def health_check():
    """
    Health check endpoint for the chatbot service.
    """
    from ...config import settings

    return {
        "status": "healthy",
        "groq_configured": bool(settings.groq_api_key),
        "tavily_configured": bool(settings.tavily_api_key),
        "serper_configured": bool(settings.serper_api_key),
    }
