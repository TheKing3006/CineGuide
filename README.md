# 🎬 CineGuide - Your AI-Powered Movie Companion

**An intelligent concierge agent for personalized movie discovery, powered by Google's Gemini 2.0 Flash and the Agent Development Kit (ADK).**

Built for the **Google Agents Intensive Capstone 2025** - Concierge Agents Track

---

## 📖 Table of Contents

- [Problem Statement](#-problem-statement)
- [Solution](#-solution)
- [Why Agents?](#-why-agents)
- [Features](#-features)
- [Architecture](#-architecture)
- [ADK Concepts Implemented](#-adk-concepts-implemented)
- [Tech Stack](#-tech-stack)
- [Setup & Installation](#-setup--installation)
- [Usage](#-usage)
- [Database](#-database)
- [Screenshots](#-screenshots)
- [Future Enhancements](#-future-enhancements)

---

## 🎯 Problem Statement

**Finding the right movie to watch is overwhelming.**

With thousands of streaming options across multiple platforms, users face:
- **Decision paralysis** from endless scrolling
- **Generic recommendations** that don't match their mood or preferences
- **Time wasted** searching instead of watching
- **Lack of personalization** in traditional recommendation engines

Existing solutions (Netflix, IMDb, Rotten Tomatoes) provide static lists or algorithm-driven suggestions that lack contextual understanding and conversational interaction.

---

## 💡 Solution

**CineGuide** is an AI-powered concierge agent that acts as your personal movie expert, offering:

- **Conversational movie discovery** - Ask in natural language ("best Hindi rom-coms" or "movies like Inception")
- **Instant detailed information** - Get comprehensive movie details including ratings, cast, plot, and awards
- **Smart randomization** - Can't decide? Use the movie roulette with customizable filters
- **700K+ movie database** - Enriched with IMDb ratings, Rotten Tomatoes scores, and complete metadata
- **Memory-enabled conversations** - The agent remembers context across interactions

---

## 🤖 Why Agents?

Traditional movie apps use static search and filter systems. **Agents make this experience intelligent and conversational:**

1. **Natural Language Understanding** - Users can ask "tell me about ddlj" and the agent understands acronyms, franchise numbers, and contextual queries

2. **Intent Recognition** - The agent parses queries to determine if users want:
   - Movie details
   - Search results
   - Top-rated lists
   - Similar recommendations
   - General conversation

3. **Dynamic Tool Selection** - The agent chooses the right database query based on user intent

4. **Contextual Memory** - Powered by ADK's memory service, the agent maintains conversation history

5. **Personalized Responses** - Gemini 2.0 Flash generates human-like, enthusiastic responses tailored to each query

---

## ✨ Features

### 🗣️ **Conversational Chat Interface**
- Ask about any movie from 700K+ titles
- Natural language queries with acronym support (e.g., "ddlj", "lotr 2", "avengers 3")
- Get comprehensive movie details including:
  - IMDb & Rotten Tomatoes ratings
  - Cast & crew information
  - Plot summary
  - Awards & box office data
  - Direct IMDb links

### 🔍 **Intelligent Search**
- Search by title, genre, or keyword
- Smart genre normalization (e.g., "scary" → "horror", "romcom" → "romance")
- Language-aware filtering (Hindi, English, Spanish, etc.)

### ⭐ **Top Movies Lists**
- Filter by genre (action, comedy, drama, etc.)
- Filter by language
- Customizable result limits (top 5, 10, 20, etc.)

### 🎯 **Similar Movie Recommendations**
- Find movies similar to your favorites
- Based on genre and rating proximity

### 🎰 **Movie Roulette**
- Random movie picker with filters:
  - Genre
  - Language
  - Year range
- Visual spinning wheel animation
- Get 3 random suggestions per spin

---

## 🏗️ Architecture

┌─────────────────────────────────────────────────────────────┐
│ CineGuide Application │
└─────────────────────────────────────────────────────────────┘
│
┌───────────────────┴───────────────────┐
│ │
▼ ▼
┌──────────────────┐ ┌──────────────────┐
│ GUI Layer │ │ Agent Layer │
│ (Tkinter) │ │ (ADK + Gemini) │
└──────────────────┘ └──────────────────┘
│ │
│ User Query │
└──────────────────┬────────────────────┘
│
▼
┌────────────────┐
│ Query Parser │
│ (Intent │
│ Recognition) │
└────────────────┘
│
┌──────────────────┼──────────────────┐
│ │ │
▼ ▼ ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Database │ │ Gemini │ │ Memory │
│ Tools │ │ Agent │ │ Service │
│ │ │ │ │ │
│ - Movie │ │ - Natural │ │ - Session │
│ Lookup │ │ Language │ │ History │
│ - Search │ │ Generation │ │ - Context │
│ - Top Lists │ │ - Response │ │ Retention │
│ - Similar │ │ Synthesis │ │ │
│ - Random │ │ │ │ │
└──────────────┘ └──────────────┘ └──────────────┘
│
▼
┌─────────────────────────────────┐
│ SQLite Database (1.12 GB) │
│ - 700K+ movies │
│ - Enriched metadata │
│ - IMDb + Rotten Tomatoes data │
└─────────────────────────────────┘


### **Data Flow:**

1. **User Input** → GUI captures natural language query
2. **Intent Recognition** → Parser determines query type (movie details, search, top lists, etc.)
3. **Tool Selection** → Appropriate database function is called
4. **Agent Reasoning** → Gemini processes conversational queries
5. **Memory Integration** → Session service maintains context
6. **Response Generation** → Results formatted and displayed

---

## 🎓 ADK Concepts Implemented

This project demonstrates **5+ key ADK concepts** from the Agents Intensive course:

### 1. **Agent Creation & Configuration**
root_agent = Agent(
model=MODEL_NAME,
name='cineguide_agent',
description='Friendly movie assistant',
instruction='You are a friendly and enthusiastic movie assistant...'
)


### 2. **Session Management**
session_service = InMemorySessionService()
await session_service.create_session(
app_name="cineguide_app",
user_id=self.user_id,
session_id=self.session_id
)


### 3. **Memory Service**
memory_service = InMemoryMemoryService()
async def auto_save_to_memory(callback_context):
await callback_context._invocation_context.memory_service.add_session_to_memory(
callback_context._invocation_context.session
)


### 4. **Runner & Async Execution**
runner = Runner(
agent=root_agent,
app_name="cineguide_app",
session_service=session_service,
memory_service=memory_service,
)

async for event in runner.run_async(
user_id=self.user_id,
session_id=self.session_id,
new_message=message
):
# Process streaming responses


### 5. **Tool Integration (Custom Database Functions)**
- `get_movie_from_db_direct()` - Movie lookup
- `search_movies()` - Search functionality
- `get_top_movies()` - Ranked lists
- `get_similar_movies()` - Recommendations
- `get_random_movies()` - Randomization

### 6. **Query Parsing & Intent Recognition**
- Pattern matching for user queries
- Acronym expansion (ddlj → Dilwale Dulhania Le Jayenge)
- Franchise number handling (star wars 5 → The Empire Strikes Back)
- Genre/language normalization

---

## 🛠️ Tech Stack

- **AI Framework**: Google Agent Development Kit (ADK)
- **LLM**: Gemini 2.0 Flash
- **Database**: SQLite (1.12 GB, 700K+ movies)
- **GUI**: Tkinter with custom dark mode theme
- **Data Source**: OMDB API (enriched dataset)
- **Language**: Python 3.8+

---

## 🚀 Setup & Installation

### *Prerequisites*
Python 3.8 or higher

Anaconda (recommended) or pip

Google API Key (Gemini)

### *Installation Steps*

Option 1: Using Anaconda (Recommended)
# Clone the repository

git clone https://github.com/YOUR_USERNAME/cineguide.git
cd cineguide

Create and activate Anaconda environment

# Create new environment
conda create -n cineguide python=3.10

# Activate environment
conda activate cineguide

# Install dependencies

pip install -r requirements.txt

# Set up environment variables

# Create .env file
cp .env.example .env

# Edit .env and add your Google API key
# On Windows: notepad .env
# On Mac/Linux: nano .env
Add this line to .env:

GOOGLE_API_KEY=your_api_key_here

# Run the application

python cineguide.py


Option 2: Using pip (Standard Python)
# Clone the repository

git clone https://github.com/YOUR_USERNAME/cineguide.git
cd cineguide

# Create virtual environment (optional but recommended)

# Create virtual environment
python -m venv venv

# Activate on Windows
venv\Scripts\activate

# Activate on Mac/Linux
source venv/bin/activate

# Install dependencies

pip install -r requirements.txt

# Set up environment variables

# Create .env file from template
cp .env.example .env

# Edit .env and add your Google API key

Run the application

python cineguide.py

That's it! The database is included, so the app launches immediately.


## 🎮 Usage

### **Chat Mode**
1. Click "Let's Talk Movies!"
2. Ask anything:
   - `"Tell me about Inception"`
   - `"Best Hindi movies"`
   - `"Top 10 action movies"`
   - `"ddlj"` (acronyms work!)
   - `"Movies like The Matrix"`

### **Roulette Mode**
1. Click "I Can't Decide..."
2. Set optional filters (genre, language, year range)
3. Click "SPIN THE ROULETTE!"
4. Get 3 random movie suggestions

---

## 💾 Database

The included `movies.db` contains:
- **700,000+ movies**
- **Metadata**: Title, year, runtime, genre, rating, language, country
- **Ratings**: IMDb (rating + votes), Rotten Tomatoes (critics + audience)
- **People**: Directors, writers, actors
- **Content**: Plot summaries, awards, box office data
- **Links**: IMDb IDs for direct access

**Size**: 1.12 GB  
**Format**: SQLite  
**Pre-processed**: All NULL values fixed, data enriched and validated

---

## 📸 Screenshots

### Title Screen
![Title Screen](screenshots/title_screen.png)

### Chat Interface
![Chat Interface](screenshots/chat_screen.png)

### Movie Roulette
![Movie Roulette](screenshots/roulette_screen.png)

---

## 🔮 Future Enhancements

- **Multi-agent architecture** - Separate agents for search, recommendations, trivia
- **Streaming service integration** - "Where can I watch this?"
- **Personalized watch history** - Track what you've seen
- **Social features** - Share recommendations with friends
- **Voice interface** - Ask with voice commands
- **Mood-based recommendations** - "I'm feeling nostalgic"
- **Cloud deployment** - Deploy to Google Cloud Run with Agent Engine

---

## 📝 License

MIT License - Free to use and modify

---

## 🙏 Acknowledgments

- **Google Agents Intensive Course** - For the ADK framework and training
- **OMDB API** - For movie metadata
- **Gemini 2.0 Flash** - For conversational intelligence

---

**Built with ❤️ for the Google Agents Intensive Capstone 2025**
~ Rishabh Bhatnagar

*Track: Concierge Agents*