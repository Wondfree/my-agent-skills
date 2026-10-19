# Reuse-First — cross-project design gate

Before designing or implementing a **new reusable capability, general-purpose infrastructure, automation workflow, data collection/monitoring component, or material technology choice**, run a proportional Stop-and-Search:

1. Check what the current project already has, then consult the Personal System Toolbox when it is available and relevant.
2. Check applicable official APIs/SDKs and standards, maintained open-source solutions, and practical managed options. A Toolbox miss is **not** evidence that external solutions do not exist.
3. Compare suitable candidates against building in-house: requirement fit, maintenance and freshness, license, security/privacy/permissions, integration effort, long-term support and operating cost. State the concrete reason to build when reusable options are unsuitable. If sources or external search are unavailable, mark the gap; never claim an exhaustive search.
4. Present reuse / combination / build / defer and evidence for **Human approval of consequential choices** before committing to a new technical route or implementation. Discovery does not grant permission to install, test against external services, expand scope, or modify other repositories.

Use the installed `reuse-first` Skill for the detailed workflow when relevant. Keep comparison evidence in the existing project design/decision record; use Toolbox for generic tool knowledge and cross-project findings rather than cloning a second catalog.

**Review gate:** When reviewing a design that builds an applicable general capability, check whether external alternatives and Build vs Reuse were investigated. Missing material evidence is a blocking design-review finding; explicitly approved exceptions, unknowns, and access limitations must be disclosed.

**Exclusions:** Ordinary bug fixes, narrow patches, well-specified local features, and routine use of an already chosen dependency do not require a broad market/open-source survey. Match research depth to impact and reversibility. Do not add a new approval system or recurring automation.
