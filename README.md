# ResearchPilotAI

### A Multi-Agent Research Intelligence Framework for Autonomous Scientific Discovery and Knowledge Synthesis

ResearchPilotAI is a research intelligence platform designed to support scientific discovery, document understanding, knowledge retrieval, and research content generation.

The system combines **Large Language Models (LLM)** with **Retrieval-Augmented Generation (RAG)** to produce context-aware responses from uploaded research documents and support structured research workflows.

---

## Overview

ResearchPilotAI provides an integrated environment for working with research documents and generating structured research outputs.

The platform supports:

- Conversational research assistance
- Research document analysis
- Retrieval-Augmented Generation (RAG)
- Evidence-grounded document question answering
- Research agents and research tools
- Topic and research-gap analysis
- Literature review generation
- Abstract generation
- Citation generation
- Research report generation
- DOCX document generation
- PPT presentation generation
- Chat history and dashboard statistics

---

## Key Features

### LLM-Based Research Intelligence

Uses an LLM as the core reasoning and generation component for:

- Research conversations
- Content synthesis
- Document-based question answering
- Research assistance
- Structured research generation

### Retrieval-Augmented Generation

The RAG pipeline processes uploaded documents through:

1. Document processing
2. Text extraction
3. Text chunking
4. Vector embedding generation
5. Vector storage
6. Similarity-based retrieval
7. Context-grounded LLM generation

This allows responses to be generated using relevant information retrieved from the user's research documents.

### Research Intelligence

ResearchPilotAI provides specialized research capabilities including:

- Research Agent
- Topic Generator
- Research Gap Analysis
- Literature Review
- Abstract Generation
- Research Synthesis
- Citation Generation

### Research Document Processing

Supported research workflows include:

- PDF upload and analysis
- Page-aware document retrieval
- Evidence-based document questioning
- Research report generation
- DOCX generation
- PPT generation

### Citation Generation

Citation formats supported:

- APA
- IEEE
- MLA

### Dashboard

Provides application-level statistics and activity information.

---

## System Architecture

![alt text](<ResearchPilotAI System Architecture.png>)

---

## Technology Stack
# Backend
- Python
- Flask
# AI
- Large Language Model (LLM)
- Ollama
- Retrieval-Augmented Generation (RAG)
- Vector Embeddings
- Similarity-based Retrieval
# Document Processing
- PDF processing
- DOCX generation
- PPT generation
# Frontend
- HTML
- CSS
- JavaScript
# Data & Storage
- SQLite
- Vector embeddings
- Local document storage

---

## Research Workflow

![alt text](<Research Workflow Infographic.png>)

---

## Security
ResearchPilotAI follows basic application security practices including:
- Environment-based configuration
- No hard-coded credentials
- Input validation
- Controlled file handling
- Bounded request and upload processing
- Error handling without exposing raw server exceptions
- Local processing through Ollama
- .gitignore protection for environment files and generated data
Do not upload API keys, passwords, private research documents, or other sensitive information to the repository.

---

## Current Limitations
- The current implementation supports research agents and agent-based workflows, but full cooperative multi-agent orchestration is still an area for further development.
- The evaluation dataset is intended for development and testing rather than a scientific benchmark.
- The authentication interface is currently a frontend demonstration.
- Production-scale distributed execution and asynchronous task processing are not currently implemented.

---

## Future Development
Potential research directions include:
- Cooperative multi-agent orchestration
- Claim-level evidence verification
- Advanced research planning
- Improved retrieval and reranking
- Hybrid retrieval
- Research knowledge graphs
- Long-term research workspaces
- Automated evaluation pipelines
- Distributed task execution
- Production deployment

---

## Author
Nikhil Murugan D P