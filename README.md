# AI Procurement Assistant

## Overview

This project is an AI-powered procurement assistant that allows users to query procurement data using natural language.

## Features

- Total spending calculation
- Top suppliers by spending
- Most frequent items
- Orders by year (e.g., 2013)
- Highest spending quarter

## Tech Stack

- Backend: FastAPI (Python)
- Database: MongoDB
- AI: OpenAI (via LangChain)
- Frontend: HTML, CSS, JavaScript

## Setup Instructions

### Backend

```bash
pip install fastapi uvicorn pymongo langchain openai python-dotenv
uvicorn backend.main:app --reload
```
