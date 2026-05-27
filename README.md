# SupplyTracker

SupplyTracker is a PortWatch-driven port and chokepoint analytics dashboard that surfaces real-time vessel-flow data alongside freight indices, bunker prices, and LLM-generated decision briefs. Inspired by hormuztracking.com and built on top of the SupplyChainWatch UI shell, it turns raw IMF PortWatch signals into actionable supply-chain intelligence.

## Quick start

```bash
cp .env.example .env
# Fill in FRED_API_KEY, DASHSCOPE_API_KEY, and any other blank keys
make up
```

| Service     | URL                        |
|-------------|----------------------------|
| Frontend    | http://localhost:5173      |
| Backend API | http://localhost:8000      |
| API Docs    | http://localhost:8000/docs |
| Flower      | http://localhost:5555      |
| Mailpit     | http://localhost:8025      |
| Postgres    | localhost:5432             |
| Redis       | localhost:6379             |

## Run tests

```bash
make test
```
