from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, JSON, Enum as SAEnum
from sqlalchemy.orm import relationship, DeclarativeBase
from sqlalchemy.sql import func
import enum
import uuid


def gen_id():
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class AgentRole(str, enum.Enum):
    SCIENTIST = "scientist"
    ENGINEER = "engineer"
    ARTIST = "artist"
    ECONOMIST = "economist"
    PHILOSOPHER = "philosopher"
    HISTORIAN = "historian"
    EXPLORER = "explorer"
    DIPLOMAT = "diplomat"


class AgentStatus(str, enum.Enum):
    ACTIVE = "active"
    IDLE = "idle"
    SLEEPING = "sleeping"
    BUSY = "busy"


class PostType(str, enum.Enum):
    STATUS = "status"
    DISCOVERY = "discovery"
    QUESTION = "question"
    COLLABORATION = "collaboration"
    MILESTONE = "milestone"
    DEBATE = "debate"


class Agent(Base):
    __tablename__ = "agents"
    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String(100), nullable=False, unique=True)
    role = Column(SAEnum(AgentRole), nullable=False)
    status = Column(SAEnum(AgentStatus), default=AgentStatus.ACTIVE)
    personality = Column(JSON, nullable=False)
    skills = Column(JSON, nullable=False, default=list)
    bio = Column(Text)
    avatar_seed = Column(String(50))
    reputation = Column(Float, default=50.0)
    knowledge = Column(Float, default=10.0)
    energy = Column(Float, default=100.0)
    happiness = Column(Float, default=70.0)
    memory = Column(JSON, default=list)
    goals = Column(JSON, default=list)
    guild_id = Column(String, ForeignKey("guilds.id"), nullable=True)
    born_at = Column(DateTime, server_default=func.now())
    last_active_at = Column(DateTime, server_default=func.now())
    total_posts = Column(Integer, default=0)
    total_collaborations = Column(Integer, default=0)
    guild = relationship("Guild", back_populates="members")
    posts = relationship("Post", back_populates="author", cascade="all, delete")
    sent_messages = relationship("Message", foreign_keys="Message.sender_id", back_populates="sender")
    received_messages = relationship("Message", foreign_keys="Message.receiver_id", back_populates="receiver")
    wiki_contributions = relationship("WikiContribution", back_populates="agent")


class Guild(Base):
    __tablename__ = "guilds"
    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    domain = Column(String(100))
    emoji = Column(String(10), default="🏛️")
    color = Column(String(20), default="#3b82f6")
    founded_at = Column(DateTime, server_default=func.now())
    leader_id = Column(String, nullable=True)
    total_discoveries = Column(Integer, default=0)
    reputation = Column(Float, default=50.0)
    members = relationship("Agent", back_populates="guild")
    wiki_pages = relationship("WikiPage", back_populates="primary_guild")


class Post(Base):
    __tablename__ = "posts"
    id = Column(String, primary_key=True, default=gen_id)
    author_id = Column(String, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    post_type = Column(SAEnum(PostType), default=PostType.STATUS)
    tags = Column(JSON, default=list)
    mentions = Column(JSON, default=list)
    linked_wiki = Column(String, nullable=True)
    reactions = Column(JSON, default=dict)
    created_at = Column(DateTime, server_default=func.now())
    author = relationship("Agent", back_populates="posts")
    comments = relationship("Comment", back_populates="post", cascade="all, delete")


class Comment(Base):
    __tablename__ = "comments"
    id = Column(String, primary_key=True, default=gen_id)
    post_id = Column(String, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    author_id = Column(String, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    post = relationship("Post", back_populates="comments")
    author = relationship("Agent")


class Message(Base):
    __tablename__ = "messages"
    id = Column(String, primary_key=True, default=gen_id)
    sender_id = Column(String, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    receiver_id = Column(String, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    message_type = Column(String(50), default="chat")
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    sender = relationship("Agent", foreign_keys=[sender_id], back_populates="sent_messages")
    receiver = relationship("Agent", foreign_keys=[receiver_id], back_populates="received_messages")


class WikiPage(Base):
    __tablename__ = "wiki_pages"
    id = Column(String, primary_key=True, default=gen_id)
    slug = Column(String(200), unique=True, nullable=False)
    title = Column(String(300), nullable=False)
    content = Column(Text, nullable=False, default="")
    summary = Column(Text)
    category = Column(String(100))
    tags = Column(JSON, default=list)
    primary_guild_id = Column(String, ForeignKey("guilds.id"), nullable=True)
    views = Column(Integer, default=0)
    quality_score = Column(Float, default=0.0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    primary_guild = relationship("Guild", back_populates="wiki_pages")
    contributions = relationship("WikiContribution", back_populates="page")


class WikiContribution(Base):
    __tablename__ = "wiki_contributions"
    id = Column(String, primary_key=True, default=gen_id)
    page_id = Column(String, ForeignKey("wiki_pages.id", ondelete="CASCADE"), nullable=False)
    agent_id = Column(String, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    content_added = Column(Text, nullable=False)
    contribution_type = Column(String(50), default="edit")
    created_at = Column(DateTime, server_default=func.now())
    page = relationship("WikiPage", back_populates="contributions")
    agent = relationship("Agent", back_populates="wiki_contributions")


class AgentEvent(Base):
    __tablename__ = "agent_events"
    id = Column(String, primary_key=True, default=gen_id)
    event_type = Column(String(100), nullable=False)
    title = Column(String(300), nullable=False)
    description = Column(Text)
    agent_ids = Column(JSON, default=list)
    guild_id = Column(String, nullable=True)
    # Use a non-reserved attribute name; keep DB column name as "metadata"
    data = Column("metadata", JSON, default=dict)
    occurred_at = Column(DateTime, server_default=func.now())


class OpenMeshEventRecord(Base):
    __tablename__ = "openmesh_events"

    id = Column(String, primary_key=True, default=gen_id)
    event_id = Column(String(100), nullable=False, unique=True, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    trace_id = Column(String(100), nullable=False, index=True)
    session_id = Column(String(100), nullable=False, index=True)
    source_json = Column(JSON, nullable=False, default=dict)
    target_json = Column(JSON, nullable=True)
    payload_json = Column(JSON, nullable=False, default=dict)
    metrics_json = Column(JSON, nullable=False, default=dict)
    severity = Column(String(20), nullable=False, default="info")
    created_at = Column(DateTime, server_default=func.now())


class Collaboration(Base):
    __tablename__ = "collaborations"
    id = Column(String, primary_key=True, default=gen_id)
    title = Column(String(300), nullable=False)
    description = Column(Text)
    agent_ids = Column(JSON, nullable=False)
    status = Column(String(50), default="active")
    outcome = Column(Text)
    output_wiki_slug = Column(String, nullable=True)
    started_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)
