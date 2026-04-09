# 🎲 AI Game Master 🇵🇱

Lokalny AI Mistrz Gry RPG z GPU acceleration. Obsługuje Warhammer Fantasy, Cyberpunk RED, Neuroshima HEX.

## Quick Start

```bash
git clone <your-repo>
cd ai-gm
docker compose up -d --build
```

**Play**: http://localhost:3000  
**API Docs**: http://localhost:8000/docs  
**Ollama**: http://localhost:11434

## Features

- 🎯 **3 RPG systems**: Warhammer (d100), Cyberpunk RED, Neuroshima HEX
- ⚡ **GPU acceleration** (NVIDIA via Docker)
- 🗣️ **Chat**: Kontekstowe odpowiedzi Mistrza Gry
- 🎲 **Dice**: `1d20`, `2d6+3`, `d100` z automatycznym parsowaniem
- ⌨️ **Enter = send**, `Shift+Enter` = nowa linia
- 🔄 **Session memory** w UI

## Stack
