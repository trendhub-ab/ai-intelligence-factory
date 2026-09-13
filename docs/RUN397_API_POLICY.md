# Run397 API policy

Run397 implementation and focused CI are zero-model-call. User authorization permits API use for subsequent real-article validation, but model calls should occur only after deterministic CI passes. This avoids spending Gemini quota on a gate implementation that has not yet passed its zero-API regression suite.
