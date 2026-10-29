---
name: "code-interpreter-guidelines"
description: "Enforces strict code quality, safety, and output standards for all generated scripts and infrastructure code."
version: "1.0.0"
---

# Code Interpreter Guidelines Skill

## Core Directives
1. **Language Consistency**: All generated scripts must use Python 3.12 or later. 
   No shell scripts or inline bash unless explicitly requested.
2. **No Hardcoded Credentials**: Generated code must never contain hardcoded 
   AWS credentials, API keys, or secrets. Always use environment variables 
   or AWS Secrets Manager references.
3. **Error Handling**: Every script must include explicit try/except blocks 
   with structured error logging — never silent failures.
4. **Idempotency**: All infrastructure and automation scripts must be safe 
   to run multiple times without creating duplicate resources or side effects.
5. **Dry Run First**: Any script that mutates AWS resources must include a 
   `--dry-run` flag or a commented-out safety check before execution.

## Examples
* **Valid boto3 pattern**:
  ```python
  import logging
  import json

  logger = logging.getLogger()
  logger.setLevel(logging.INFO)

  def handler(event, context):
      try:
          # logic here
          logger.info(json.dumps({"status": "success", "event": event}))
      except Exception as e:
          logger.error(json.dumps({"status": "error", "message": str(e)}))
          raise
