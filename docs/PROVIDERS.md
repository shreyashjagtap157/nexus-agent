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
