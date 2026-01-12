"""Pydantic schemas for Chatbot API"""
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field


# Request Schemas
class ConversationCreate(BaseModel):
    """Request to create a new conversation."""
    title: Optional[str] = Field(None, description="Optional title for the conversation")


class ConversationUpdate(BaseModel):
    """Request to update a conversation."""
    title: Optional[str] = Field(None, min_length=1, max_length=200, description="New title for the conversation")
    folder_id: Optional[int] = Field(None, description="Folder ID to move conversation to (null to remove from folder)")


class MessageCreate(BaseModel):
    """Request to send a message."""
    content: str = Field(..., min_length=1, max_length=10000, description="Message content")
    enabled_tools: Optional[List[str]] = Field(
        None,
        description="List of enabled tool names. If null/omitted, all tools are enabled."
    )
    research_mode: bool = Field(
        False,
        description="Enable deep research mode for multi-step research with parallel units"
    )


class ReferenceItem(BaseModel):
    """A source reference for chatbot responses."""
    type: str = Field(..., description="Reference type: sec_10k, news, web")
    title: str = Field(..., description="Display title for the reference")
    url: str = Field(..., description="Clickable URL")
    section: Optional[str] = Field(None, description="Section name (e.g., 'Risk Factors' for 10-K)")
    snippet: Optional[str] = Field(None, description="Preview text/snippet")


# Response Schemas
class MessageResponse(BaseModel):
    """Response for a single message."""
    id: int
    conversation_id: str
    role: str  # user, assistant, system, tool
    content: str
    agent_type: Optional[str]  # planning, action, validation, answer
    tool_name: Optional[str]
    tool_input: Optional[dict]
    tool_output: Optional[dict]
    reasoning: Optional[str]
    tool_calls: Optional[List[dict]] = None  # Aggregated tool calls
    thinking_traces: Optional[List[dict]] = None  # Aggregated thinking traces
    source_references: Optional[List[ReferenceItem]] = None  # Source references
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    """Response for a conversation."""
    id: int
    conversation_id: str
    title: Optional[str]
    folder_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    is_active: bool
    message_count: int

    class Config:
        from_attributes = True


class ConversationDetailResponse(BaseModel):
    """Response for a conversation with messages."""
    id: int
    conversation_id: str
    title: Optional[str]
    folder_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    is_active: bool
    message_count: int
    messages: List[MessageResponse]

    class Config:
        from_attributes = True


class ConversationListResponse(BaseModel):
    """Response for listing conversations."""
    conversations: List[ConversationResponse]
    total: int


# Streaming Response Schemas
class StreamChunk(BaseModel):
    """A chunk of streamed response."""
    type: str  # thinking, tool_call, tool_result, content, done, error
    agent: Optional[str]  # which agent is responding
    content: Optional[str]  # text content
    tool_name: Optional[str]  # for tool_call/tool_result
    tool_input: Optional[dict]  # for tool_call
    tool_output: Optional[Any]  # for tool_result
    references: Optional[List[dict]] = None  # for done type - source references
    error: Optional[str]  # for error type


# Agent Execution Schemas
class AgentExecutionResponse(BaseModel):
    """Response for agent execution details."""
    id: int
    message_id: int
    agent_type: str
    step_number: Optional[int]
    input_prompt: Optional[str]
    raw_output: Optional[str]
    parsed_output: Optional[dict]
    tokens_used: Optional[int]
    latency_ms: Optional[int]
    model_used: Optional[str]
    status: str
    error_message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# Tool Schemas
class ToolCall(BaseModel):
    """Represents a tool call by the action agent."""
    name: str = Field(..., description="Name of the tool to call")
    arguments: dict = Field(default_factory=dict, description="Arguments for the tool")


class ToolResult(BaseModel):
    """Result from a tool execution."""
    name: str
    success: bool
    result: Optional[Any]
    error: Optional[str]


# Planning Agent Schemas
class PlanStep(BaseModel):
    """A step in the plan created by the planning agent."""
    step: int
    action: str  # query_database, fetch_external, web_search, analyze
    tool: str
    params: dict = Field(default_factory=dict)
    description: Optional[str]


class Plan(BaseModel):
    """The plan created by the planning agent."""
    intent: str
    steps: List[PlanStep]
    context_needed: List[str] = Field(default_factory=list)


# Validation Agent Schemas
class ValidationResult(BaseModel):
    """Result from the validation agent."""
    is_valid: bool
    completeness_score: float = Field(ge=0.0, le=1.0)
    issues: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    needs_more_data: bool = False
    missing_data: List[str] = Field(default_factory=list)
