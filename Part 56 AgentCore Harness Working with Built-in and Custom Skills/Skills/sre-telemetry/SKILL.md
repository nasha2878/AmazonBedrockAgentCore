---
name: "sre-telemetry"
description: "Enforces mandatory logging, CloudWatch log streams, and metric-based health tracking structures for deployed components."
version: "1.0.0"
---

# SRE Telemetry Skill

## Core Directives
1. **Structured Logging**: All code outputs must explicitly implement structured JSON logging formats rather than plain-text strings.
2. **Observability Infrastructure**: Every infrastructure script must provision an explicitly attached log group or monitoring stream with a retention period matching standard environments (exactly 14 days for test/lab workloads).
3. **Dead-Letter Queues (DLQ)**: Any event-driven pipelines or messaging nodes (like SNS or SQS handles) must configure an active Dead-Letter Queue to systematically trap unhandled message drops.

## Examples
* **Valid S3 Logging Config (CDK)**:
  ```python
  server_access_logs_prefix="access-logs/",
  ```