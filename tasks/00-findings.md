- Docker network name: ai-net          → .env LLM_NETWORK
- llama-server scrape target: <name>:8080  → prometheus.yml (literal, per correction #1)
- Metric names present:
  - throughput:
      llamacpp:prompt_tokens_seconds
      llamacpp:predicted_tokens_seconds

  - requests:
      llamacpp:requests_processing
      llamacpp:requests_deferred

  - counters:
      llamacpp:prompt_tokens_total
      llamacpp:prompt_seconds_total
      llamacpp:tokens_predicted_total
      llamacpp:tokens_predicted_seconds_total
      llamacpp:n_decode_total
      llamacpp:n_busy_slots_per_decode

  - context:
      llamacpp:n_tokens_max

  - speculative:
      llamacpp:spec_decode_num_draft_tokens_total
      llamacpp:spec_decode_num_accepted_tokens_total
      llamacpp:spec_decode_num_drafts_total
      llamacpp:spec_decode_num_accepted_tokens_per_pos_total