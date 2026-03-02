# Asclepius Research Labs — Web Application

Production full-stack AI web app for autoimmune disease research.

## Stack

| Layer    | Technology                         |
|----------|------------------------------------|
| Backend  | Python · FastAPI · Pydantic · Uvicorn |
| Frontend | Next.js 14 (App Router) · TypeScript · TailwindCSS · Axios |

---

## Project Structure

```
autoimmune_intelligence/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI application factory, CORS middleware
│   │   ├── api/
│   │   │   └── routes.py        # POST /query endpoint
│   │   ├── core/
│   │   │   └── config.py        # BaseSettings environment configuration
│   │   ├── services/
│   │   │   └── llm_service.py   # LLM service class (stubbed, OpenAI-ready)
│   │   └── models/
│   │       └── schema.py        # Pydantic request/response schemas
│   └── requirements.txt
└── frontend/
    ├── app/
    │   ├── layout.tsx            # Root layout
    │   ├── page.tsx              # Landing page with query form
    │   └── globals.css           # TailwindCSS base styles
    ├── components/
    │   └── ResponseCard.tsx      # Response display component
    ├── lib/
    │   └── api.ts                # Axios API client with typed interfaces
    ├── package.json
    ├── tsconfig.json
    ├── tailwind.config.js
    ├── postcss.config.js
    ├── next.config.js
    └── .env.local.example
```

---

## Quick Start

### 1. Backend

```bash
cd autoimmune_intelligence/backend

# Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# (Optional) Configure environment variables
cp .env.example .env            # edit OPENAI_API_KEY etc.

# Start the development server
uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`.  
Interactive docs: `http://localhost:8000/docs`.

### 2. Frontend

```bash
cd autoimmune_intelligence/frontend

# Install dependencies
npm install

# Configure the API URL
cp .env.local.example .env.local   # edit NEXT_PUBLIC_API_URL if needed

# Start the development server
npm run dev
```

The UI will be available at `http://localhost:3000`.

---

## API

### `POST /query`

**Request**

```json
{ "question": "What drives JAK-STAT dysregulation in lupus?" }
```

**Response**

```json
{
  "answer": "Based on current immunological research …",
  "sources": [
    "Firestein GS. Nature. 2003;423:356-361.",
    "Tanaka T, et al. J Clin Med. 2016;5(2):14."
  ]
}
```

### `GET /health`

Returns `{ "status": "healthy", "service": "Asclepius Research Labs" }`.

---

## Environment Variables

### Backend (`.env`)

| Variable        | Default                   | Description                     |
|-----------------|---------------------------|---------------------------------|
| `APP_NAME`      | `Asclepius Research Labs` | Service display name            |
| `OPENAI_API_KEY`| *(empty)*                 | OpenAI API key (when wired up)  |
| `LLM_MODEL`     | `gpt-4o`                  | Model identifier                |
| `CORS_ORIGINS`  | `["*"]`                   | Allowed CORS origins            |
| `LOG_LEVEL`     | `INFO`                    | Python logging level            |

### Frontend (`.env.local`)

| Variable               | Default                   | Description          |
|------------------------|---------------------------|----------------------|
| `NEXT_PUBLIC_API_URL`  | `http://localhost:8000`   | Backend API base URL |

---

## Plugging In a Real LLM

Open `backend/app/services/llm_service.py` and replace the `_call_llm` method
body with your provider call, for example:

```python
from openai import OpenAI
from app.core.config import settings

client = OpenAI(api_key=settings.openai_api_key)

def _call_llm(self, question: str) -> tuple[str, list[str]]:
    completion = client.chat.completions.create(
        model=settings.llm_model,
        messages=[{"role": "user", "content": question}],
    )
    answer = completion.choices[0].message.content or ""
    return answer, []
```

No other files need to change.
