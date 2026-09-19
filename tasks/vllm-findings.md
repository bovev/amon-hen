- Container: vllm-mxfp4-qwen38 (dual R9700), serves on port 8080 inside the container
  (published to the host as 127.0.0.1:8080)
- Network at time of findings: default `bridge` only — must join ai-net with alias vllm-server
- vllm-server scrape target: vllm-server:8080   → prometheus.yml (literal, per correction #1)
- Speculative decoding: on
- Not yet confirmed: vLLM version, label names on the series, HTTP status of /metrics once
  --api-key is set (expected 200 — the key only guards /v1/*)
- Metric families present (sample suffixes _bucket/_count/_sum/_created omitted;
  mirrored in scripts/checks/vllm_panels.py CONFIRMED_METRICS):
  - requests / scheduler:
      vllm:num_requests_running
      vllm:num_requests_waiting
      vllm:num_requests_waiting_by_reason
      vllm:num_preemptions_total
      vllm:request_success_total
      vllm:iteration_tokens_total                      (histogram)
      vllm:engine_sleep_state

  - kv / prefix cache:
      vllm:kv_cache_usage_perc
      vllm:cache_config_info
      vllm:prefix_cache_hits_total
      vllm:prefix_cache_queries_total
      vllm:external_prefix_cache_hits_total
      vllm:external_prefix_cache_queries_total
      vllm:mm_cache_hits_total
      vllm:mm_cache_queries_total

  - tokens:
      vllm:prompt_tokens_total
      vllm:prompt_tokens_by_source_total
      vllm:prompt_tokens_cached_total
      vllm:generation_tokens_total

  - latency (histograms):
      vllm:time_to_first_token_seconds
      vllm:inter_token_latency_seconds
      vllm:e2e_request_latency_seconds
      vllm:request_queue_time_seconds
      vllm:request_prefill_time_seconds
      vllm:request_decode_time_seconds
      vllm:request_inference_time_seconds
      vllm:request_time_per_output_token_seconds

  - request shape (histograms):
      vllm:request_prompt_tokens
      vllm:request_generation_tokens
      vllm:request_max_num_generation_tokens
      vllm:request_params_max_tokens
      vllm:request_params_n
      vllm:request_prefill_kv_computed_tokens

  - speculative:
      vllm:spec_decode_num_draft_tokens_total
      vllm:spec_decode_num_accepted_tokens_total
      vllm:spec_decode_num_drafts_total
      vllm:spec_decode_num_accepted_tokens_per_pos_total

  - other:
      vllm:estimated_flops_per_gpu_total
      vllm:estimated_read_bytes_per_gpu_total
      vllm:estimated_write_bytes_per_gpu_total
      vllm:tool_call_parser_invocations_total
