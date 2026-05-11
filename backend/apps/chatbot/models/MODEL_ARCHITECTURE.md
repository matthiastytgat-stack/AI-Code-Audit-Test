# Django Models Architecture for AI Chatbot (October 2025)

## Overview

This document explains the Django models architecture for the AI chatbot application, which integrates with **LangGraph's PostgresCheckpointer** and **pgvector** for optimal performance and feature completeness.

## Architecture Philosophy

### What We DON'T Store in Django Models

✅ **LangGraph Checkpointer** (`PG_CHECKPOINT_URI`) handles:
- Message history storage
- Conversation state/checkpoints  
- Thread management
- Automatic summarization (via SummarizationNode)

✅ **PGVector Store** (`PGVECTOR_CONNECTION_STRING`) handles:
- Document embeddings for RAG
- Semantic search on documents
- Vector similarity queries

### What We DO Store in Django Models

✅ **Django Models** (this app) handle:
- User-facing metadata (titles, descriptions)
- User preferences and settings
- Usage tracking and billing
- Tool configurations
- File upload metadata  
- Feedback and analytics

## Model Breakdown

### 1. ChatSession (Thread Metadata)

**Purpose:** Maps to LangGraph `thread_id` with user-facing metadata

**Key Fields:**
- `id` (UUID) - Also serves as LangGraph thread_id
- `user` - Foreign key to User
- `title` - User-friendly conversation title
- `model_name`, `temperature` - AI configuration
- `enable_summarization` - Auto-summarization settings
- `message_count`, `total_tokens_used` - Analytics
- `is_active`, `is_archived`, `is_pinned` - Status

**Why This Model?**
- LangGraph stores the actual messages
- We need user-friendly titles and organization
- Users need to see/manage their conversations
- Analytics tracking (costs, usage)

**Example Usage:**
```python
# Create new chat session
session = ChatSession.objects.create(
    user=request.user,
    title="Python Help",
    model_name="gpt-4o",
    temperature=0.7
)

# Use with LangGraph
config = {"configurable": {"thread_id": str(session.id)}}
response = agent.invoke({"messages": [msg]}, config)

# Update analytics
session.update_analytics(message_count=1, tokens_used=150)
```

---

### 2. UserPreference (AI Settings)

**Purpose:** Store user-specific AI preferences and defaults

**Key Fields:**
- `user` - OneToOne with User
- `default_model` - Default AI model
- `default_temperature`, `default_max_tokens` - Model settings
- `enable_auto_summarization` - Summarization preferences
- `custom_system_prompt` - User's custom prompt
- `daily_message_limit`, `daily_token_limit` - Usage limits
- `theme`, `enable_streaming` - UI preferences

**Why This Model?**
- Every user needs different default settings
- Preferences persist across sessions
- Can configure summarization behavior
- Usage limits and quotas

**Example Usage:**
```python
# Get user preferences (auto-created)
prefs = user.ai_preferences

# Get config for new session
session_config = prefs.get_session_config()

# Create session with user defaults
session = ChatSession.objects.create(
    user=user,
    **session_config
)
```

---

### 3. TokenUsage (Cost Tracking)

**Purpose:** Track AI token consumption and costs per request

**Key Fields:**
- `user`, `chat_session` - Foreign keys
- `model_name` - AI model used
- `prompt_tokens`, `completion_tokens`, `total_tokens`
- `prompt_cost`, `completion_cost`, `total_cost`
- `request_type` - chat, summarization, embedding, etc.
- `response_time_ms` - Performance metrics

**Why This Model?**
- Billing and cost analytics
- User quotas and limits
- Per-session cost tracking
- Performance monitoring

**Example Usage:**
```python
# Calculate and store usage
costs = TokenUsage.calculate_cost(
    model_name="gpt-4o",
    prompt_tokens=150,
    completion_tokens=75
)

TokenUsage.objects.create(
    user=user,
    chat_session=session,
    model_name="gpt-4o",
    prompt_tokens=150,
    completion_tokens=75,
    **costs
)

# Check user limits before request
limit_check = TokenUsage.check_user_limits(user, additional_tokens=200)
if not limit_check['allowed']:
    raise Exception(limit_check['reason'])
```

---

### 4. MessageFeedback (User Ratings)

**Purpose:** Collect user feedback on AI responses

**Key Fields:**
- `user`, `chat_session` - Foreign keys
- `checkpoint_id`, `message_index` - Identify message in LangGraph
- `rating` - thumbs up/down, stars
- `feedback_categories` - JSON list of categories
- `feedback_text` - Detailed feedback
- `reported_issue` - Issue type if reporting
- `reviewed`, `reviewed_by` - Admin review tracking

**Why This Model?**
- Quality monitoring
- User satisfaction metrics
- Issue identification
- Model improvement data

**Example Usage:**
```python
# Store feedback
MessageFeedback.objects.create(
    user=user,
    chat_session=session,
    checkpoint_id=checkpoint.id,
    message_index=2,  # AI response index
    rating='thumbs_up',
    feedback_text='Very helpful explanation!'
)

# Get session satisfaction
stats = MessageFeedback.get_session_satisfaction(session)
print(f"Satisfaction: {stats['satisfaction_rate']}%")
```

---

### 5. UserDocument (RAG Files)

**Purpose:** Track uploaded documents for RAG

**Key Fields:**
- `user`, `chat_session` - Foreign keys
- `file` - FileField for uploaded document
- `file_name`, `file_size`, `file_type`
- `processing_status` - pending, processing, completed, failed
- **`vector_collection_name`** - PGVector collection name (REQUIRED!)
- **`vector_collection_metadata`** - Optional collection-level metadata
- `vector_store_ids` - JSON list of pgvector document IDs
- **`vector_metadata`** - Searchable metadata stored with each chunk
- `chunk_count` - Number of embeddings created
- `is_active` - Enable/disable document

**Why This Model?**
- Track file uploads and processing status
- Store PGVector collection references
- Manage searchable metadata for filtering
- User document organization

**Important: Collection Names & Metadata**

Based on PGVector documentation, we MUST store:

1. **Collection Name** (Required)
   - Each document/set of embeddings belongs to a collection
   - Collection name is NOT the table name
   - Allows organizing different document sets
   - Example: `user_123_documents`, `session_abc_context`

2. **Collection Metadata** (Optional)
   - Metadata about the collection itself
   - Stored once per collection
   - Example: `{"user_id": "123", "created_at": "2025-01-01"}`

3. **Document Metadata** (Essential)
   - Metadata stored with EACH chunk/embedding
   - Used for filtering in similarity searches
   - Stored in JSONB for efficient querying
   - Example: `{"user_id": "123", "category": "research", "tags": ["python", "ai"]}`

**Example Usage:**
```python
# 1. Create document record
doc = UserDocument.objects.create(
    user=user,
    chat_session=session,
    file=uploaded_file,
    file_name=uploaded_file.name,
    file_size=uploaded_file.size,
    file_type=uploaded_file.content_type
)

# 2. Process and store in PGVector (in Celery task)
from langchain_postgres import PGVector
from langchain_openai import OpenAIEmbeddings

# Create unique collection name per user
collection_name = f"user_{user.id}_documents"

# Initialize PGVector with collection
vector_store = PGVector(
    embeddings=OpenAIEmbeddings(),
    collection_name=collection_name,  # REQUIRED!
    connection=settings.PGVECTOR_CONNECTION_STRING,
    use_jsonb=True
)

# Get metadata for each chunk
vector_metadata = doc.get_vector_metadata()  # Returns searchable dict

# Add document chunks with metadata
from langchain.text_splitter import RecursiveCharacterTextSplitter
splitter = RecursiveCharacterTextSplitter(chunk_size=1000)
chunks = splitter.split_text(document_text)

# Store with metadata for filtering
vector_ids = vector_store.add_texts(
    texts=chunks,
    metadatas=[vector_metadata] * len(chunks)  # Same metadata for all chunks
)

# 3. Mark processing completed
doc.mark_processing_completed(
    collection_name=collection_name,  # Store collection name!
    vector_ids=vector_ids,
    chunk_count=len(chunks),
    collection_metadata={"user_id": str(user.id), "doc_type": "pdf"},
    vector_metadata=vector_metadata
)

# 4. Search with metadata filtering
from langchain_postgres import PGVector

vector_store = PGVector(
    embeddings=OpenAIEmbeddings(),
    collection_name=doc.vector_collection_name,
    connection=settings.PGVECTOR_CONNECTION_STRING
)

# Filter by user_id using metadata
results = vector_store.similarity_search(
    query="What is machine learning?",
    k=5,
    filter={"user_id": {"$eq": str(user.id)}}  # Filter by metadata!
)

# 5. Get user storage
storage = UserDocument.get_user_storage_usage(user)
print(f"Using {storage['total_size_mb']} MB")

# 6. Get all documents in a collection
docs_in_collection = UserDocument.get_documents_in_collection(
    collection_name=f"user_{user.id}_documents",
    user=user
)
```

---

### 6. SystemPromptTemplate (Reusable Prompts)

**Purpose:** Catalog of system prompts for different use cases

**Key Fields:**
- `name`, `slug` - Identification
- `content` - The system prompt
- `category` - coding, writing, research, etc.
- `variables` - List of replaceable variables
- `is_default`, `is_public` - Visibility
- `usage_count`, `rating` - Analytics

**Why This Model?**
- Reusable prompts
- User can choose prompt
- Admin can create templates
- Track popularity

**Example Usage:**
```python
# Get default prompt
default_prompt = SystemPromptTemplate.get_default()

# Render with variables
prompt = default_prompt.render({
    'user_name': user.first_name,
    'topic': 'Python programming'
})

# Use in session
session.custom_system_prompt = prompt
session.save()
```

---

### 7. UserTool (Enabled Tools)

**Purpose:** Track which tools users have enabled

**Key Fields:**
- `user` - Foreign key
- `tool_name` - Internal name
- `is_enabled` - Enable/disable
- `configuration` - JSON tool config
- `usage_count`, `last_used_at` - Analytics
- `rate_limit` - Usage limits

**Why This Model?**
- Users control which tools to enable
- Per-user tool configuration
- Rate limiting
- Usage tracking

**Example Usage:**
```python
# Enable tool for user
tool = UserTool.objects.create(
    user=user,
    tool_name='web_search',
    tool_display_name='Web Search',
    configuration={'max_results': 5}
)

# Check rate limit before use
limit_check = tool.check_rate_limit()
if not limit_check['allowed']:
    raise Exception('Rate limit exceeded')

# Track usage
tool.increment_usage()
```

---

### 8. AvailableTool (Tool Catalog)

**Purpose:** Catalog of all available tools

**Key Fields:**
- `tool_name` - Internal name
- `display_name` - UI name
- `description` - What it does
- `category` - Tool category
- `is_active`, `is_public` - Availability
- `config_schema` - JSON schema for config

**Why This Model?**
- Tool marketplace
- Admin can add new tools
- Users can browse and enable

---

### 9. UserAPIKey (User Keys)

**Purpose:** Store encrypted user API keys

**Key Fields:**
- `user`, `provider` - Foreign keys
- `encrypted_key` - Encrypted API key
- `key_name`, `key_prefix` - Identification
- `is_active`, `is_default` - Status
- `usage_count`, `total_tokens_used` - Analytics
- `daily_limit`, `monthly_limit` - Quotas

**Why This Model?**
- Users can use own API keys
- Encrypted at rest (security)
- Track usage per key
- Validate keys

**Example Usage:**
```python
# Store user's API key (encrypted)
api_key = UserAPIKey.objects.create(
    user=user,
    provider='openai',
    key_name='My OpenAI Key'
)
api_key.encrypt_api_key('sk-...')  # Encrypted before saving
api_key.save()

# Validate key
result = api_key.validate_key()
if result['valid']:
    api_key.is_validated = True
    api_key.save()

# Use in request
actual_key = api_key.decrypt_api_key()
```

---

## Database Schema Summary

```
CustomUser (from accounts app)
    |
    ├── ChatSession (1-to-many)
    │   ├── TokenUsage (1-to-many)
    │   ├── MessageFeedback (1-to-many)
    │   └── UserDocument (1-to-many)
    │
    ├── UserPreference (1-to-1)
    ├── UserTool (1-to-many)
    ├── UserAPIKey (1-to-many)
    └── TokenUsage (1-to-many)

SystemPromptTemplate (standalone)
AvailableTool (standalone)
```

## Integration with LangGraph

### Creating a Chat Session

```python
from apps.chatbot.models import ChatSession
from langgraph.checkpoint.postgres import PostgresSaver
from langchain_openai import ChatOpenAI

# 1. Create Django session
session = ChatSession.objects.create(
    user=request.user,
    title="New Conversation",
    model_name="gpt-4o",
    temperature=0.7
)

# 2. Setup LangGraph with checkpointer
checkpointer = PostgresSaver.from_conn_string(
    settings.PG_CHECKPOINT_URI
)
checkpointer.setup()

# 3. Create agent
agent = create_react_agent(
    model=ChatOpenAI(model=session.model_name),
    tools=tools,
    checkpointer=checkpointer
)

# 4. Invoke with thread_id = session.id
config = {
    "configurable": {
        "thread_id": str(session.id)  # Maps to Django ChatSession
    }
}

response = agent.invoke(
    {"messages": [HumanMessage(content="Hello")]},
    config
)

# 5. Track usage
TokenUsage.objects.create(
    user=request.user,
    chat_session=session,
    # ... token counts and costs
)

# 6. Update session analytics
session.update_analytics(message_count=1, tokens_used=150)
```

### Retrieving Conversation History

```python
# Django provides metadata
session = ChatSession.objects.get(id=thread_id)

# LangGraph provides actual messages
checkpointer = PostgresSaver.from_conn_string(settings.PG_CHECKPOINT_URI)
config = {"configurable": {"thread_id": str(session.id)}}

# Get state from LangGraph
state = checkpointer.get_state(config)
messages = state['messages']

# Combine for API response
return {
    'session': {
        'id': session.id,
        'title': session.title,
        'created_at': session.created_at,
        'message_count': session.message_count,
    },
    'messages': messages  # From LangGraph
}
```

## Migration Commands

```bash
# Create migrations
python manage.py makemigrations chatbot

# Apply migrations
python manage.py migrate chatbot

# Create initial data
python manage.py shell
>>> from apps.chatbot.models import SystemPromptTemplate
>>> SystemPromptTemplate.objects.create(
...     name="Default Assistant",
...     slug="default-assistant",
...     content="You are a helpful AI assistant.",
...     is_default=True,
...     is_public=True
... )
```

## Performance Considerations

### Indexes

All models have optimized indexes on:
- Foreign keys (user, chat_session)
- Status fields (is_active, is_archived)
- Timestamp fields (created_at, updated_at)
- Composite indexes for common queries

### Caching Strategy

```python
from django.core.cache import cache

# Cache user preferences (1 hour)
prefs = cache.get(f'user_prefs_{user.id}')
if not prefs:
    prefs = user.ai_preferences
    cache.set(f'user_prefs_{user.id}', prefs, 3600)

# Cache session metadata (5 minutes)
session = cache.get(f'chat_session_{session_id}')
if not session:
    session = ChatSession.objects.get(id=session_id)
    cache.set(f'chat_session_{session_id}', session, 300)
```

### Query Optimization

```python
# Prefetch related data
sessions = ChatSession.objects.filter(user=user).select_related(
    'user'
).prefetch_related(
    'token_usage',
    'message_feedback'
)

# Annotate with aggregates
from django.db.models import Sum, Count

sessions = ChatSession.objects.filter(user=user).annotate(
    total_cost=Sum('token_usage__total_cost'),
    feedback_count=Count('message_feedback')
)
```

## Security Best Practices

1. **API Key Encryption:**
   - Use Fernet encryption for API keys
   - Store encryption key in environment variable
   - Never log decrypted keys

2. **User Data Isolation:**
   - Always filter by user
   - Use permissions on sensitive operations
   - Validate ownership before access

3. **Rate Limiting:**
   - Implement at model level (UserTool.check_rate_limit)
   - Also use Django middleware
   - Track in TokenUsage for billing

## Testing

```python
# tests/test_models.py
from django.test import TestCase
from apps.chatbot.models import ChatSession, TokenUsage

class ChatSessionTests(TestCase):
    def test_create_session(self):
        session = ChatSession.objects.create(
            user=self.user,
            title="Test Chat"
        )
        self.assertEqual(session.thread_id, str(session.id))
    
    def test_token_usage_calculation(self):
        costs = TokenUsage.calculate_cost(
            model_name="gpt-4o",
            prompt_tokens=100,
            completion_tokens=50
        )
        self.assertGreater(costs['total_cost'], 0)
```

## Next Steps

1. **Create migrations:**
   ```bash
   python manage.py makemigrations chatbot
   python manage.py migrate chatbot
   ```

2. **Create Django admin:**
   - Register all models in admin.py
   - Add list filters and search
   - Custom admin actions

3. **Create API endpoints:**
   - Django REST Framework serializers
   - ViewSets for CRUD operations
   - Integrate with LangGraph

4. **Add Celery tasks:**
   - Document processing for RAG
   - Usage analytics aggregation
   - Cleanup old sessions

5. **Create frontend components:**
   - Chat interface with session management
   - User preferences page
   - Usage analytics dashboard

---

## Summary

This Django model architecture:
- ✅ Complements LangGraph (doesn't duplicate)
- ✅ Provides user-facing features
- ✅ Tracks usage and costs
- ✅ Enables tool management
- ✅ Supports RAG with file uploads
- ✅ Collects feedback for improvement
- ✅ Manages user preferences
- ✅ Secure API key storage

**Key Principle:** Django handles what users see and configure. LangGraph handles the conversation logic.
