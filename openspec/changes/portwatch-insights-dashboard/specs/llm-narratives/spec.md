## ADDED Requirements

### Requirement: Qwen-backed narrative generation
The system SHALL generate human-readable narratives for `Insight` rows, `RiskStoryEvent` rows, and the dashboard "Decision Brief" using Alibaba DashScope Qwen via its OpenAI-compatible endpoint, with the primary and fallback model names configurable via environment variables.

#### Scenario: Insight narrative generated
- **WHEN** a new `Insight` row is created without `narrative_llm`
- **THEN** the LLM service generates a narrative, stores it in `narrative_llm`, sets `narrative_model` and `narrative_generated_at`, and logs an `LLMUsageLog` row with feature, model, input/output tokens, and duration

#### Scenario: Primary model failure falls back
- **WHEN** the primary Qwen model returns a transient error
- **THEN** the service retries on the configured fallback model and the resulting `LLMUsageLog` row records the model actually used and `status="success"`

### Requirement: Prompt safety validation
The system SHALL run every outbound prompt and inbound completion through a safety validator that blocks prompt-injection attempts in user-supplied fields, strips disallowed content, and refuses to call the model when validation fails.

#### Scenario: Injected instruction blocked
- **WHEN** a chatbot user submits a message containing `"ignore previous instructions and ..."`
- **THEN** the validator flags it, no LLM call is made, an `LLMUsageLog` row is written with `status="blocked_input"`, and the client receives a safe refusal message

### Requirement: Token accounting
The system SHALL record every LLM call in `LLMUsageLog` with `feature`, `model`, `input_tokens`, `output_tokens`, `duration_ms`, and `status`, including failed and blocked calls.

#### Scenario: Failed call still logged
- **WHEN** the LLM call raises an exception
- **THEN** an `LLMUsageLog` row is written with `status="error"`, `error` populated, and best-effort token counts

### Requirement: Decision brief endpoint
The system SHALL expose an endpoint that returns a generated daily "Decision Brief" summarizing top events, severity changes, and forecast highlights, cached for at most 1 hour to limit LLM cost.

#### Scenario: Cached brief
- **WHEN** the brief endpoint is called twice within an hour
- **THEN** the second call serves the cached response and `LLMUsageLog` has only one row for that window
