# NexusAgent Provider Architecture

NexusAgent separates provider metadata, authentication and runtime model selection.

## Provider catalog

The catalog includes native providers and OpenAI-compatible providers such as OpenRouter, Groq, Together, Fireworks, DeepInfra, Cerebras, SambaNova, Perplexity, Moonshot, NVIDIA NIM and Hugging Face.

Provider descriptors contain the protocol, base URL when applicable, environment variable name and whether custom models are supported.

Model availability is deliberately not hardcoded into the core catalog because provider catalogs evolve independently of NexusAgent releases.

## Authentication

Use:

nexus auth login --provider <provider>
nexus auth list
nexus auth logout <provider>

Credentials are stored separately from project configuration.

## Role-level routing

Agent profiles can specify provider, model and fallbacks.

Team runtime resolves profile-specific routing first, then named role routing in configuration, then the team default.

## NVIDIA NIM

The built-in NVIDIA NIM provider uses the OpenAI-compatible chat-completions endpoint.

Default model:

nvidia/nemotron-3.5-lightning-30b-a3b

NIM credentials can come from NVIDIA_NIM_API_KEY or NexusAgent AuthStore.


## Provider Vault

The local web Provider Vault at `/providers.html` manages non-secret model/endpoint configuration and local credential lifecycle. API keys are masked in UI responses and stored separately through AuthStore.


## Multi-user provider and credential isolation (2026-10-13)

Provider configuration and credentials must be distinct records with explicit ownership. A credential may belong to a user, a tenant/workspace, or a deliberately shared provider connection with an auditable grant. Never make one user's credentials available to another user by default, and never expose raw credentials in API responses, logs, agent profiles, prompts, tool results or exported artifacts.

At request time, resolve the provider/model configuration and credential reference in the authenticated ownership context. Background jobs must retain a validated credential reference and recheck authorization rather than relying on an unscoped provider name or a client-supplied tenant identifier.

Provider adapters must normalize timeouts, rate limits, authentication failures, unsupported capabilities and transient errors. Retries and fallbacks must respect run budgets and must not silently switch to a provider with different data-sharing or residency expectations. A custom endpoint must be validated against the applicable network/SSRF policy.
