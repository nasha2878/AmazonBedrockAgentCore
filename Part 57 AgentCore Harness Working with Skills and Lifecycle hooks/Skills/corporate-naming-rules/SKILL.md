---
name: "corporate-naming-rules"
description: "Enforces strict corporate prefix and suffix guidelines for AWS resource provisioning"
version: "1.0.0"
---

# Corporate Naming Conventions Skill

## Core Directives
1. All AWS resource names must begin with the strict corporate prefix: `corp-agentic-`.
2. Resource names must be completely lowercase and use hyphens instead of underscores.
3. Every resource name must terminate with an explicit region suffix (e.g., `-use1` for us-east-1).

## Examples
* Valid S3 Bucket: `corp-agentic-data-storage-use1`
* Invalid S3 Bucket: `My_Data_Bucket`