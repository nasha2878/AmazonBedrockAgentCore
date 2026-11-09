---
name: "cost-guardrails"
description: "Enforces mandatory resource tagging, auto-expiration lifecycle policies, and cost-conscious resource selection."
version: "1.0.0"
---

# Cost Guardrails Skill

## Core Directives
1. **Mandatory Tagging**: Every resource must include an explicit tagging structure:
   * `CostCenter`: `9999-agentic`
   * `Environment`: `Lab`
2. **Storage Lifecycles**: All S3 storage definitions must explicitly configure objects to transition to Infrequent Access (IA) after 30 days and permanently expire/delete after 90 days to eliminate data accumulation costs.
3. **Compute Efficiency**: If any compute resources (like EC2 or Lambda) are generated, they must be set to the lowest cost tier suitable for testing, and explicitly document an auto-stop schedule or a short execution timeout window (maximum 15 seconds for Lambda).

## Examples
* **Valid S3 Lifecycle Snippet (CDK)**:
  ```python
  lifecycle_rules=[
      s3.LifecycleRule(
          enabled=True,
          transitions=[s3.Transition(storage_class=s3.StorageClass.INFREQUENT_ACCESS, transition_after=Duration.days(30))],
          expiration=Duration.days(90)
      )
  ]
  ```