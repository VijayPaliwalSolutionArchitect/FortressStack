"""FortressStack Gateway — a minimal, private, OpenAI-compatible LLM gateway.

This is the self-contained 'backend' service of FortressStack: an OpenAI-compatible
proxy that fronts local Ollama models and enforces local-mode egress rules. It exists
so the stack can run with zero external data flow even without the heavier LiteLLM
governance gateway.

Design pillars
--------------
1. Local-only by default — ``local_mode: true`` refuses to proxy any request to an
   external host. This is the compliance proof FortressStack sells.
2. Model allowlist — only models listed in ``backend/config/gateway.yaml`` are
   served. Unknown models are rejected before any network call.
3. OpenAI-compatible surface — ``/v1/models``, ``/v1/chat/completions``,
   ``/v1/embeddings`` so existing OpenAI SDK clients work unchanged.
"""

__version__ = "1.0.0"