# Review scope

Use this guide for core application functionality.

This area should contain framework-independent logic, such as:

- domain models
- application services
- mode routing
- prompt construction
- model profile selection
- configuration models
- shared errors
- ports/interfaces

## App rules

App code must remain independent of delivery and infrastructure frameworks.

Do not import:

- FastAPI
- Chainlit
- Redis
- RQ
- SQLAlchemy session objects
- llama-server HTTP clients
- Docker/Compose-specific logic

App code may define ports/interfaces that the infrastructure implements.

## Expected patterns

Use:

- service layer for use cases
- ports/adapters for external systems
- typed request/result objects
- explicit errors
- small, testable functions/classes

Avoid:

- global mutable state
- hidden I/O
- direct environment variable reads scattered through core logic
- generic `utils.py` dumping grounds
- importing concrete adapters from application services

## LLM behaviour

Core logic may decide that an LLM call is needed, but it must make the call through an abstraction such as `LLMGateway`.

Core logic must not call llama-server directly.

Core logic must not assume one model forever. It may select a model profile or mode, but concrete model runtime details belong outside the core.

## Model profiles

Profile selection should be deterministic and testable.

Expected modes include:

- default
- intent
- translation
- definition
- learning
- general

Unknown modes should fall back to the default unless the feature explicitly requires rejection.

## Tests

App tests should use fakes/mocks.

They should not require:

- Redis
- PostgreSQL
- llama-server
- GPU
- Docker

Review for clear unit tests around mode routing, prompt construction, profile selection, validation, and error handling.
