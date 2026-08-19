# Local LLM Monitoring

This project provides a lightweight monitoring setup for a locally hosted llama.cpp inference server.

Its purpose is to make LLM activity and performance easy to understand at a glance. Prometheus collects metrics from the server, while Grafana presents them in a local dashboard.

The project focuses on:

- LLM inference performance and request activity
- A small resource footprint
- Local-only access by default
- Reproducible, file-based configuration
- A foundation that can support additional monitoring later

The initial version is limited to Prometheus, Grafana OSS, and an LLM overview dashboard. The implementation is currently being planned and documented.
Goal is to build Amon Hen of local LLM monitoring, a "Hill of Seeing."
