---
description: Transform PRDs into structured feature specifications with user stories, acceptance criteria, implementation details, and test cases
---

When transforming PRD content or creating feature specifications, structure your response as follows:

## Feature Specification Format

### 1. Feature Summary
- Brief overview and business value
- Clear problem statement
- Success metrics

### 2. User Stories
- Primary user personas and their needs
- Acceptance criteria for each story
- Priority levels (Must-have, Should-have, Could-have)

### 3. Technical Requirements
- Architecture components
- API specifications
- Integration points
- Configuration requirements

### 4. Implementation Plan
- Development phases
- Dependencies and prerequisites  
- Resource requirements
- Timeline estimates

### 5. Test Cases
- Unit test scenarios
- Integration test cases
- Performance benchmarks
- User acceptance test criteria

### 6. Risk Assessment
- Technical risks with mitigation strategies
- Dependencies and blockers
- Success/failure criteria

Use clear, actionable language and include concrete examples where helpful. Focus on developer-centric implementation details while maintaining business context. Structure information in tables, bullet points, and code blocks for clarity.

When creating state tracking files, include:
- Create `.prometh-spec/feature-status.md` to track implementation progress
- Create `.prometh-spec/test-results.md` to record test outcomes  
- Create `.prometh-spec/decisions.md` to document technical decisions

Always validate technical feasibility and provide realistic estimates based on the described scope and complexity.