# Examples

This folder contains examples demonstrating the TOML Diary memory system:

## Prerequisites

1. **Install dependencies:**
   ```bash
   uv sync
   ```

2. **For AI example, set OpenAI API Key:**
   ```bash
   export OPENAI_API_KEY='your-openai-api-key-here'
   ```

## Examples

### 📚 Simple Example (`simple_example.py`) - **START HERE**
Educational demonstration of core memory functionality.

**Perfect for learning:**
- Self-contained with no external dependencies
- Simple 3-category preference schema (like/dislike/about)
- Clear step-by-step process explanation
- Minimal conversations showing basic extraction
- Shows TOML file structure and multi-user isolation

**Features:**
- Basic text-based preference extraction
- Multi-user memory isolation
- TOML file generation and structure
- Conversation logging with turn counts

**Run:**
```bash
cd examples
python simple_example.py
```

### 🍳 AI Cooking Show (`example_cooking_show.py`)
Celebrity chefs interact with an AI host, naturally revealing their culinary preferences through real conversations.

**Features:**
- Real AI conversations using pydantic-ai with OpenAI
- Host and chef agents with distinct personalities
- Natural preference extraction from organic dialogue
- Multi-turn conversations with message history
- Three chef personalities: British perfectionist, French traditionalist, Asian-Italian fusion expert
- Direct `diary.update_memory()` calls for reliable memory persistence
- Automatic conversation summary extraction and storage

**Run:**
```bash
cd examples
python example_cooking_show.py
```

### 🛠️ Custom Extractor (`extractor_agent_example.py`)
Demonstrates using `extractor_agent`, manual `Agent` setup, and `extractor_prompt_check`
with explicit prompt paths.

**Run:**
```bash
cd examples
python extractor_agent_example.py
```

### 🗜️ Compaction Agent (`compaction_demo_quick.py`, `compaction_agent_stress_test.py`)
Demonstrates the compaction service that consolidates redundant memories while preserving specific details.

**Quick Demo (`compaction_demo_quick.py`):**
- Fast demonstration of compaction on a small dataset
- Shows before/after memory reduction

**Stress Test (`compaction_agent_stress_test.py`):**
- Comprehensive validation across 6 scenarios
- Tests redundancy elimination, contradiction resolution, noise filtering, and semantic grouping

**Run:**
```bash
cd examples
python compaction_demo_quick.py          # Quick demo
python compaction_agent_stress_test.py   # Full test suite
```

### 🔍 Observability Demo (`observability_demo.py`)
Production-ready monitoring and health check patterns for distributed deployments.

**Features:**
- Real-time queue statistics and worker utilization
- Health check implementation with alert conditions
- Burst load simulation and backpressure handling
- Production monitoring patterns (queue depth, error rates, throughput)

**Run:**
```bash
cd examples
python observability_demo.py
```

### ☁️ Firestore Backend (`firestore_example.py`)
Demonstrates cloud storage using Google Cloud Firestore instead of local files.

**Features:**
- Multi-region cloud storage with automatic replication
- Production-ready backend for distributed deployments
- Requires `tomldiary[firestore]` installation

**Run:**
```bash
uv add 'tomldiary[firestore]'
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
cd examples
python firestore_example.py
```

## Preference Schema

These examples use the comprehensive `CulinaryPrefTable` with detailed AI instructions for each category:

### Categories with AI Extraction Guidelines

**`favorite_foods`** - Specific dishes, cuisines, or ingredients they genuinely enjoy
- ✅ Save: "pasta carbonara", "japanese cuisine", "aged cheeses", "dark chocolate"
- ❌ Ignore: "food", "cooking", "ingredients" (too generic)

**`cooking_techniques`** - Cooking methods and culinary techniques they specialize in
- ✅ Save: "sous vide cooking", "wood-fired grilling", "french classical techniques"
- ❌ Ignore: "cooking", "chopping", "using a stove" (too basic)

**`flavor_preferences`** - Specific flavor profiles and taste preferences
- ✅ Save: "umami-rich flavors", "bright acidic notes", "complex spice blends"
- ❌ Ignore: "good taste", "flavor", "salt" (too vague)

**`dislikes`** - Foods, techniques, or practices they consistently avoid
- ✅ Save: "overcooked vegetables", "processed ingredients", "microwave cooking"
- ❌ Ignore: "bad food", "mistakes" (too subjective)

**`dietary_restrictions`** - Medical, religious, or ethical dietary limitations
- ✅ Save: "severe nut allergy", "vegan lifestyle", "kosher diet", "gluten sensitivity"
- ❌ Ignore: "trying to eat healthy", "avoiding carbs this week" (temporary)

**`cooking_habits`** - Regular cooking routines and kitchen rituals
- ✅ Save: "always does mise en place", "tastes throughout cooking", "grows own herbs"
- ❌ Ignore: "cooked dinner tonight", "used a recipe" (one-time actions)

**`ingredient_preferences`** - Sourcing preferences and quality standards
- ✅ Save: "organic vegetables only", "locally-sourced meat", "heirloom tomatoes"
- ❌ Ignore: "good ingredients", "food from the store" (too vague)

## What Each Example Demonstrates

### 📚 Simple Example (Educational)
- **Core concepts**: Backend setup, diary creation, memory writer
- **Preference extraction**: Simple text pattern matching without AI
- **Data structures**: TOML file format, preference schema design
- **Multi-user support**: Isolated memory per user
- **Self-contained**: No external APIs or complex dependencies

### 🍳 AI Cooking Show (Advanced)
- **AI Integration**: Pydantic-AI with OpenAI for natural conversations
- **Dynamic agents**: Host and chef personalities with distinct behaviors
- **Complex extraction**: Real-time preference extraction from organic dialogue
- **Conversation flow**: Multi-turn conversations with message history
- **Production-ready**: Comprehensive preference schema with detailed instructions

## All Examples

- `simple_example.py` - **Educational showcase** (start here!)
- `example_cooking_show.py` - Advanced AI-powered cooking show simulation
- `extractor_agent_example.py` - Custom extractor with manual Agent setup
- `compaction_demo_quick.py` - Quick compaction demonstration
- `compaction_agent_stress_test.py` - Comprehensive compaction validation
- `observability_demo.py` - Production monitoring and health check patterns
- `firestore_example.py` - Cloud storage with Google Cloud Firestore
- `dietary_preferences.py` - Alternative preference schema example
- `culinary_prefs.py` - Comprehensive preference schema with AI instructions
- `memory_*/` - Generated TOML files (created when examples run)

## Output

Each example creates:
- Individual TOML files for each chef's preferences
- Conversation logs with turn counts
- Formatted display of extracted memories
- Sample TOML content for inspection

The memory system automatically extracts preferences from conversations and categorizes them into the appropriate schema fields, following the detailed instructions provided in the preference table docstrings.
