## ADDED Requirements

### Requirement: Chat backend SHALL ground responses in the active entity's chart data

When the chat endpoint receives an `entity_context` referencing a port or chokepoint, the LLM prompt SHALL include a compact structured summary of that entity's latest risk score, recent metric trends (latest, window mean, window max), latest forecast, relevant macro indices, and any active disruption-propagation rows.

#### Scenario: Port context includes trend stats and indices

- **WHEN** the chatbot is invoked with `entity_context=[{entity_type:"port", entity_id:"SGSIN"}]`
- **THEN** the prompt assembled by `_fetch_entity_context` contains a "Risk" line (latest, 30d mean, 30d max), a "Vessel count latest" line, an "Avg dwell hours" line, a "Forecast (next 7d)" line with band, an "Indices" line with FBX/WCI values and 7d % change, and any "Active disruptions" count

#### Scenario: Chokepoint context includes propagation

- **WHEN** the chatbot is invoked with `entity_context=[{entity_type:"chokepoint", entity_id:"hormuz"}]`
- **THEN** the prompt includes the chokepoint's risk + trend, plus a list of downstream ports from `disruption_propagation` where the chokepoint is the source

#### Scenario: Multiple entities supported

- **WHEN** `entity_context` contains two entities
- **THEN** each entity gets its own block in the prompt, separated by a blank line

#### Scenario: Missing data does not break the prompt

- **WHEN** an entity has no risk score, no recent events, or no forecast
- **THEN** the prompt omits the missing lines and continues with whatever data is available; the request returns a normal streamed response

### Requirement: Chat backend SHALL bound the size of the grounded context

The assembled context SHALL be capped to avoid blowing the LLM token budget.

#### Scenario: Per-entity cap

- **WHEN** an entity has very large narratives or many disruption rows
- **THEN** each entity's block is truncated to approximately 600 tokens (with a clear "(truncated)" marker if applicable)

#### Scenario: Total cap

- **WHEN** the combined entity blocks would exceed approximately 2500 tokens
- **THEN** later entities are dropped (oldest selection priority) and a note is appended indicating context truncation

### Requirement: Frontend SHALL send `entity_context` as an array

The `ChatRequest.entity_context` field in the frontend type definitions SHALL be an array of `{ entity_type, entity_id, entity_name? }` objects (possibly empty), matching the backend contract.

#### Scenario: Sending from a port detail view

- **WHEN** the user opens the chatbot from `#/ports/SGSIN`
- **THEN** the outgoing request body has `entity_context: [{ entity_type: "port", entity_id: "SGSIN" }]`

#### Scenario: Sending from a chokepoint detail view

- **WHEN** the user opens the chatbot from `#/chokepoints/hormuz`
- **THEN** the outgoing request body has `entity_context: [{ entity_type: "chokepoint", entity_id: "hormuz" }]`

#### Scenario: Sending from a non-detail route

- **WHEN** the user opens the chatbot from a route that is not a port/chokepoint detail
- **THEN** the outgoing request body has `entity_context: []`

### Requirement: Backend SHALL accept the legacy single-object `entity_context` shape during transition

For one release window, the chat endpoint SHALL accept both the array shape and the legacy single-object shape and normalise internally.

#### Scenario: Legacy single object

- **WHEN** a request body arrives with `entity_context: { entity_type: "port", entity_id: "SGSIN" }`
- **THEN** the backend coerces it into a one-element array and proceeds with the same grounded-context behaviour
