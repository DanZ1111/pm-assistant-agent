from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from database import Base


class Entity(Base):
    __tablename__ = "entities"

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String, nullable=False)  # 'project', 'idea', or 'context'
    visibility = Column(String, nullable=False, default="workspace")  # workspace | restricted
    title = Column(Text, nullable=False)
    status = Column(String, default="active")  # active, dormant, done, archived
    product_phase = Column(String, nullable=True)
    marketing_phase = Column(String, nullable=True)
    priority = Column(String, nullable=True)   # low, medium, high, urgent — only set explicitly
    target_date = Column(String, nullable=True)  # ISO date string — only set explicitly
    short_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    records = relationship("EntityRecord", back_populates="entity", cascade="all, delete-orphan")


class EntityRecord(Base):
    __tablename__ = "entity_records"

    id = Column(Integer, primary_key=True, index=True)
    entity_id = Column(Integer, ForeignKey("entities.id"), nullable=False)
    record_type = Column(String, nullable=False)  # soft preferred set, not a DB enum
    content = Column(Text, nullable=False)
    structured_data = Column(JSON, nullable=True)
    source = Column(String, default="chat")  # 'chat' or 'system'
    created_at = Column(DateTime, default=datetime.utcnow)

    entity = relationship("Entity", back_populates="records")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False, default="viewer")  # owner | editor | viewer
    created_at = Column(DateTime, default=datetime.utcnow)

    conversations = relationship("Conversation", back_populates="user")


class EntityLink(Base):
    __tablename__ = "entity_links"

    id = Column(Integer, primary_key=True, index=True)
    from_entity_id = Column(Integer, ForeignKey("entities.id"), nullable=False)
    to_entity_id = Column(Integer, ForeignKey("entities.id"), nullable=False)
    link_type = Column(String, nullable=False)  # 'inspired_by' or 'related_to'
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(String, nullable=False)  # user, assistant, tool
    content = Column(Text, nullable=True)  # nullable — assistant messages may have no text when using tools
    tool_calls = Column(Text, nullable=True)  # JSON string for assistant messages with tool use
    tool_call_id = Column(String, nullable=True)  # for tool result messages
    tool_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")
