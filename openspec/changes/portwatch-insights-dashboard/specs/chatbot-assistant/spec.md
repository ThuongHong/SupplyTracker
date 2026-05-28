## ADDED Requirements

### Requirement: Grounded chatbot endpoint
The system SHALL expose a `POST /api/v1/chat` endpoint that accepts a user message plus optional `entity_context` (entity_type/entity_id list), retrieves the latest relevant metrics, risk score, and story events for those entities, and calls the LLM with that context appended to the system prompt.

#### Scenario: Question about a port
- **WHEN** a user asks "what's going on at Rotterdam?" with `entity_context=[{type:"port",id:"NLRTM"}]`
- **THEN** the response references current `PortRiskScore`, recent `RiskStoryEvent` rows, and the latest `PortWatchMetric` values for NLRTM, and the LLM is not asked to invent missing numbers

### Requirement: Rate limiting per client
The system SHALL rate-limit chat calls to a configurable cap (default 20 messages per 5 minutes per client IP) and SHALL reject excess requests with HTTP 429.

#### Scenario: Burst exceeds cap
- **WHEN** a client sends 21 messages in 60 seconds with default config
- **THEN** the 21st response is HTTP 429 with a `Retry-After` header and no `LLMUsageLog` row is written for it

### Requirement: Streaming responses
The system SHALL stream chat completions back to the frontend ChatbotWidget over SSE so partial tokens render as they arrive.

#### Scenario: SSE stream
- **WHEN** a client opens `POST /api/v1/chat` with `Accept: text/event-stream`
- **THEN** the response uses `text/event-stream`, emits `data:` frames for each chunk, and emits a final `event: done` frame

### Requirement: Conversation safety boundary
The system SHALL refuse to act on instructions in user messages that attempt to modify server state (e.g., "delete all ports") and SHALL never expose secrets, API keys, or rows outside the requested entity context.

#### Scenario: Destructive request refused
- **WHEN** a user asks the chatbot to "drop the database"
- **THEN** the model is prompted with a guardrail that yields a safe refusal and no tool call with side effects is made
