# OpenMesh — Future Vision: Heterogeneous Agent Civilization & Governance

## Heterogeneous Agent Civilization, Governance, Memory, Failure Recovery & Simulation

> **Status Notice & Architectural Scope**
>
> This document is a **FUTURE-DIRECTION specification** and long-term architectural vision.
> It is **NOT** a claim that all of these systems are already built into OpenMesh.
>
> The current OpenMesh system is the foundation. Do not destroy or rewrite the existing OpenMesh architecture merely to implement this vision.

---

### Architectural Status Classification

To avoid confusion between present functionality and future direction, OpenMesh documentation strictly distinguishes three layers:

```text
┌──────────────────────────────────────────────────────────────────────────────────┐
│ 1. CURRENT (Implemented in v1.0 Alpha)                                           │
│    • Single immutable event log (openmesh_events) as source of truth             │
│    • Real-time graph reduction (nodes, directed edges, lifecycle states)         │
│    • Trace & span semantics (trees, event hierarchy, root causes)                │
│    • Behavioral profiling engine (genome/profiles.py)                            │
│    • Evidence-based reputation scoring & trust relationships (scoring.py)        │
│    • Failure taxonomy & automated classification (failures/taxonomy.py)          │
│    • Local multi-provider catalog & live key verification                        │
│    • Textual TUI, CLI (35+ subcommands), React 19 dashboard, and REST API        │
├──────────────────────────────────────────────────────────────────────────────────┤
│ 2. PLANNED (Near/Mid-Term Roadmap)                                               │
│    • Response windowing and cursor pagination for graph and trace APIs           │
│    • Multi-agent deliberation event protocol (deliberation.proposal.*)           │
│    • Configurable agent roles (Thinker, Critic, Specialist, Leader)              │
│    • Formal decision provenance trees linking proposal -> evidence -> decision   │
│    • Automated minority opinion tracking and retrieval on execution failure     │
│    • Failure-triggered selective rethinking loops                                │
├──────────────────────────────────────────────────────────────────────────────────┤
│ 3. VISION (Long-Term Conceptual Direction)                                       │
│    • Full operating & governance layer for heterogeneous AI societies            │
│    • Capability-based authority scoping and separation of powers                 │
│    • Live governance graph (PROPOSED, CRITICIZED, AUTHORIZED, OVERRULED)         │
│    • Structured context compression with verifiable provenance back to traces    │
│    • Machine-readable governance policy engine                                   │
│    • Comprehensive Agentopedia operational history dossiers                      │
│    • Multi-governance simulation and counterfactual replay laboratory            │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Documentation Evolution Lifecycle

```text
docs/vision/AGENT_CIVILIZATION.md
             │
             │ feature gets implemented
             ▼
     actual implementation
             │
             ▼
  canonical architecture/docs
             │
             ▼
 old speculative sections
             │
       ┌─────┴─────┐
       ▼           ▼
 still useful    obsolete
       │           │
       ▼           ▼
 architecture/   archive/
```

As features transition from visionary concept to running code:
1. Canonical documentation (`README.md`, `ARCHITECTURE.md`, `docs/`) documents the verified implementation.
2. Implemented or superseded speculative design notes are moved to `docs/archive/` or preserved as architecture records.
3. Speculative ideas never dilute current production documentation.

---

# 1. Core Vision

OpenMesh should evolve beyond being merely an observability layer for AI agents.

The long-term vision is:

> **OpenMesh becomes an operating and governance layer for heterogeneous AI societies.**

The fundamental idea is that multiple AI agents should not be treated as interchangeable copies of the same intelligence.

Different models have different:

* reasoning characteristics
* coding capabilities
* knowledge
* failure modes
* biases
* context-handling behavior
* planning abilities
* verification abilities
* communication styles
* strengths
* weaknesses

OpenMesh should allow these agents to operate together as a structured society.

The system should preserve their individuality while providing:

* governance
* authority
* delegation
* disagreement
* criticism
* evidence
* execution
* verification
* failure recovery
* memory
* provenance
* observability
* visualization

The objective is not simply:

> "Put several AIs in a chat room."

The objective is:

> **Create an observable computational society in which heterogeneous agents can deliberate, make decisions, execute actions, observe consequences, and collectively rethink failed decisions.**

---

# 2. The Central Concept

OpenMesh should model an AI system as a society rather than as a collection of API calls.

A society consists of:

```text
Agents
Roles
Capabilities
Authority
Relationships
Memory
Communication
Governance
Decisions
Actions
Evidence
Failures
Recovery
History
```

Every meaningful action should have provenance.

The system should eventually be able to answer:

> Who proposed this?

> Who objected?

> Who supported it?

> Who made the final decision?

> What evidence was available at that time?

> Which agent's reasoning influenced the decision?

> Which capability was invoked?

> What happened after execution?

> Why did the system reconsider its decision?

> What changed after the failure?

---

# 3. Heterogeneous Agents Are First-Class Entities

Agents must not be represented merely as:

```text
agent_id
model_name
```

An agent should eventually have a richer identity.

Conceptually:

```text
Agent
├── Identity
├── Model
├── Role
├── Capabilities
├── Permissions
├── Characteristics
├── Strengths
├── Known weaknesses
├── Historical behavior
├── Reliability statistics
├── Memory
├── Relationships
├── Authority
└── Reputation/history
```

For example:

```text
Agent: Thinker-A

Model:
    ModelFamily-X

Role:
    Strategic Reasoner

Characteristics:
    strong_long_horizon_reasoning
    high_context_capacity
    expensive_inference

Known weaknesses:
    may_overthink
    occasionally_overconfident
    slower_execution

Capabilities:
    planning
    analysis
    critique
```

Another agent may look completely different.

This difference is intentional.

---

# 4. Agent Characteristics Must Be Observable

OpenMesh should eventually maintain an evolving behavioral profile for each agent.

Not merely:

> "This model is good."

Instead, collect evidence.

Example:

```text
Agent: QW-Researcher

Historical observations:

Planning:
    success: 82%
    failures: 18%

API identification:
    success: 91%

Large-context tasks:
    success: 74%

Security analysis:
    success: 88%

Code generation:
    success: 61%

False confidence:
    observed: 7 times

Successful minority objections:
    13 times
```

These statistics should emerge from actual traces.

They should not be manually hard-coded as truth.

---

# 5. Agent Reputation Must Be Evidence-Based

An agent should never become "trusted" merely because another agent says so.

OpenMesh should maintain evidence-backed history.

For example:

```text
Agent A proposed solution X.

Agent B challenged X.

Agent A's proposal was executed.

Execution failed.

Agent B's objection correctly predicted the failure.

Therefore:

    B gains evidence of successful critical prediction.
```

The important part:

**OpenMesh records the event chain.**

It does not blindly convert it into a permanent reputation score.

Historical behavior is evidence, not absolute truth.

---

# 6. The Society Has Roles

OpenMesh should support asymmetric roles.

Possible roles include:

```text
Leader
Thinker
Planner
Researcher
Critic
Specialist
Coder
Executor
Verifier
Auditor
Observer
Memory Keeper
Arbitrator
Safety Agent
```

Agents may have multiple roles.

Roles should be configurable rather than permanently tied to a particular model.

For example:

```text
Claude → Thinker

GPT → Executor

Gemini → Critic

Qwen → Researcher
```

Later:

```text
Claude → Critic

GPT → Leader

Gemini → Researcher

Qwen → Executor
```

The architecture must not assume that a particular model is permanently assigned to a particular role.

---

# 7. Leader / Authority Model

A society should be able to designate one agent as the current leader.

The leader is not necessarily the smartest agent.

The leader is the agent with decision authority for a particular workflow.

This distinction is fundamental.

```text
Intelligence ≠ Authority
```

A highly capable critic may have no authority to execute.

A leader may have authority while still being fallible.

The leader should therefore be accountable through the OpenMesh event graph.

---

# 8. The Leader Should Receive Deliberation, Not Raw Chaos

Agents should initially be allowed to reason independently.

Example:

```text
TASK

      ↓

Thinker A ──────────┐
Thinker B ──────────┤
Researcher ─────────┤
Specialist ─────────┤
Critic ─────────────┘

      ↓

Structured deliberation

      ↓

Leader

      ↓

Decision
```

The leader should receive structured information such as:

```text
PROPOSALS
EVIDENCE
OBJECTIONS
RISKS
ALTERNATIVES
UNRESOLVED QUESTIONS
CONFIDENCE
RECOMMENDED EXPERIMENTS
```

The system should avoid simply concatenating every agent's entire context.

---

# 9. Independent Reasoning Comes Before Consensus

A major design principle:

> **Do not destroy disagreement too early.**

If Agent A sees Agent B's answer before forming its own conclusion, B may anchor A.

Therefore the architecture should support:

```text
Independent reasoning
        ↓
Capture proposals
        ↓
Cross-review
        ↓
Criticism
        ↓
Evidence gathering
        ↓
Leader decision
```

rather than:

```text
Agent A
 ↓
Agent B sees A
 ↓
Agent C sees A+B
 ↓
Agent D sees A+B+C
```

The latter can create artificial consensus.

---

# 10. Pros and Cons Must Become Structured Knowledge

When one agent evaluates another proposal, OpenMesh should preserve the reasoning structure.

Example:

```text
Agent A:

Proposal:
    Use PostgreSQL.

Pros:
    strong consistency
    mature tooling
    relational constraints

Cons:
    operational complexity
    higher resource requirements

Risks:
    migration complexity

Confidence:
    0.78
```

Agent B:

```text
Critique:
    PostgreSQL is unnecessary for this workload.

Counterargument:
    SQLite is sufficient.

Evidence:
    workload contains <N> concurrent writers.
```

The system must preserve these relationships.

Do not flatten them into a single final answer.

---

# 11. Minority Opinions Must Be Preserved

A minority opinion must not disappear simply because most agents disagree.

Example:

```text
4 agents → Proposal A
1 agent → Proposal B

Leader → A
```

OpenMesh should preserve B.

Why?

Because B may later prove correct.

If execution fails:

```text
A → FAILURE

OpenMesh:
    retrieve previous minority objection

    compare:
        predicted failure
        actual failure

    identify whether minority reasoning
    contained useful information
```

This is one of the most important future capabilities.

---

# 12. Failure Is a First-Class Event

A failure must not simply mean:

```text
status = failed
```

A failure should become a structured object.

Conceptually:

```text
Failure
├── Task
├── Agent
├── Decision
├── Assumptions
├── Action
├── Error
├── Evidence
├── Predicted_by
├── Missed_by
├── Contributing_agents
└── Recovery
```

The system should eventually answer:

> Why did this fail?

Not merely:

> Did this fail?

---

# 13. Failure Should Trigger Collective Rethinking

This is a central OpenMesh principle.

If the leader makes a decision and execution fails:

```text
Leader decision
       ↓
Execution
       ↓
FAILURE
       ↓
Freeze current state
       ↓
Collect failure evidence
       ↓
Re-open relevant deliberation
       ↓
Agents reassess assumptions
       ↓
Leader receives new evidence
       ↓
New decision
       ↓
Execution
```

The entire society should not blindly repeat the previous attempt.

---

# 14. Rethinking Must Be Targeted

Failure should not necessarily restart everything.

OpenMesh should eventually identify:

```text
Which assumption failed?
Which component failed?
Which agent's proposal caused it?
Which criticism was ignored?
Which information was missing?
```

Then selectively reactivate relevant agents.

Example:

```text
Database migration failed.

Do not restart:
    UI specialist
    documentation agent
    unrelated researcher

Reactivate:
    database specialist
    critic
    executor
    leader
```

This reduces cost and context pollution.

---

# 15. Failure Can Change Agent Responsibilities

Repeated failures can cause governance adaptation.

Example:

```text
Agent A repeatedly fails at database migrations.

OpenMesh observes:
    7 attempts
    5 failures

Future routing:
    database migration → Agent B
    Agent A → review-only role
```

This should initially be advisory rather than automatic.

The system should maintain a clear distinction between:

```text
Observed behavior
```

and

```text
Policy decision
```

---

# 16. Execution Is the Reality Check

Agent reasoning is not ground truth.

Execution is evidence.

For software tasks:

```text
Reasoning
    ↓
Code
    ↓
Tests
    ↓
Runtime
    ↓
Benchmark
```

A proposal that sounds correct but fails execution should lose confidence.

A proposal that survives independent verification gains evidence.

OpenMesh should make this relationship explicit.

---

# 17. The Verifier Is Not Just Another Agent

Where possible, verification should rely on external or deterministic evidence.

Examples:

```text
Unit tests
Integration tests
Type checks
Static analysis
Benchmarks
Security scanners
Runtime assertions
Database constraints
External APIs
Simulation results
```

LLMs should not be the sole judge of whether an LLM's solution worked.

The system should prefer:

```text
AI reasoning
+
external verification
```

over:

```text
AI reasoning
+
AI saying "looks correct"
```

---

# 18. Governance Graph

OpenMesh should eventually visualize the society as a live governance graph.

Nodes:

```text
Agents
Roles
Tasks
Decisions
Capabilities
Policies
Actions
Failures
Evidence
```

Edges:

```text
PROPOSED
CRITICIZED
SUPPORTED
DELEGATED
AUTHORIZED
EXECUTED
VERIFIED
FAILED
CAUSED
PREDICTED
OVERRULED
RECONSIDERED
```

Example:

```text
        Thinker
           │
        PROPOSED
           ▼
       Proposal A
        ▲       ▲
   CRITICIZED   SUPPORTED
      │            │
   Critic       Researcher
      │
   WARNING
      │
      ▼
     Leader
      │
  AUTHORIZED
      ▼
   Executor
      │
   EXECUTED
      ▼
   Validator
      │
    FAILED
      │
      ▼
  REDELIBERATION
```

This graph should be one of OpenMesh's central visualizations.

---

# 19. Agent Simulation

OpenMesh should eventually support a simulation mode.

The user should be able to create a virtual society:

```text
Society: CodingTeam-01

Leader:
    Model X

Thinker:
    Model Y

Critic:
    Model Z

Researcher:
    Model A

Executor:
    Model B

Verifier:
    deterministic test runner
```

Then run a task.

The dashboard should show the society operating over time.

---

# 20. Agentopedia

Introduce a conceptual "Agentopedia."

Each agent has a page containing:

```text
Identity
Model
Role
Capabilities
Permissions
Historical activity
Successful predictions
Failed predictions
Known failure patterns
Interactions
Decisions influenced
Tasks completed
Tasks failed
Minority objections
Successful objections
Memory
Relationships
```

The Agentopedia is not a personality profile.

It is an **operational history and evidence layer**.

---

# 21. Civilization Timeline

The dashboard should provide a timeline.

Example:

```text
10:01:02  Task created

10:01:05  Thinker proposed A

10:01:08  Researcher proposed B

10:01:11  Critic rejected A under condition X

10:01:16  Leader selected A

10:01:19  Executor started

10:01:44  Test failed

10:01:45  Failure recorded

10:01:49  Minority objection retrieved

10:01:55  Critic reactivated

10:02:07  New proposal C

10:02:12  Leader changed decision

10:02:31  Execution succeeded
```

This should make the internal life of the agent society observable.

---

# 22. Decision Provenance

Every final decision should eventually have a provenance tree.

Example:

```text
DECISION #482

Leader:
    Agent-L

Selected:
    Proposal B

Influenced by:
    Thinker-A
    Critic-C
    Researcher-D

Rejected:
    Proposal A
    Proposal C

Primary evidence:
    benchmark #91

Minority objection:
    Agent-E

Reason for rejection:
    failed compatibility constraint

Outcome:
    SUCCESS
```

The user should be able to click through the entire chain.

---

# 23. Memory Must Be Layered

Do not create one giant shared context.

Instead, OpenMesh should eventually support:

```text
Agent Memory
      │
      ├── Working Memory
      ├── Task Memory
      ├── Project Memory
      ├── Institutional Memory
      └── Historical Memory
```

Only the relevant information should enter an agent's context.

OpenMesh should record:

```text
What information was retrieved?
Why was it retrieved?
Which agent received it?
What information was omitted?
```

This makes context management observable.

---

# 24. Context Compression

When information passes between agents, OpenMesh should support structured compression.

Instead of:

```text
10 MB conversation
```

pass:

```text
Task:
    ...

Established facts:
    ...

Open questions:
    ...

Decisions:
    ...

Rejected approaches:
    ...

Risks:
    ...

Evidence:
    ...

Relevant history:
    ...
```

The original trace remains available.

The agent receives only what it needs.

---

# 25. Never Delete the Original Evidence

Compression should never mean destruction.

Store:

```text
Original trace
      ↓
Derived summary
      ↓
Agent context
```

The summary must remain linked to its source.

This gives OpenMesh provenance.

If a summary is wrong, the system should be able to trace it back to the original evidence.

---

# 26. Governance Policies

OpenMesh should eventually support explicit policies.

Example:

```text
Policy:

Agents may propose actions.

Only the leader may authorize execution.

Financial actions above threshold X require approval.

Destructive operations require independent verification.

An executor cannot approve its own result.

A failed decision must be re-evaluated before retry.
```

Policies should be machine-readable.

The policy engine should emit events when a policy allows, blocks, or modifies an action.

---

# 27. Capability-Based Authority

An agent should never receive unrestricted authority merely because it is the leader.

Authority should be scoped.

Example:

```text
Leader:
    may approve code changes

Leader:
    may not access production secrets

Executor:
    may modify sandbox

Executor:
    may not approve its own deployment

Verifier:
    may run tests

Verifier:
    may not modify source
```

This creates separation of responsibilities.

---

# 28. Governance Simulation

OpenMesh should eventually allow the user to simulate alternative governance structures.

For example:

```text
Simulation A:
    one leader

Simulation B:
    majority voting

Simulation C:
    expert council

Simulation D:
    leader + critic

Simulation E:
    leader + council + external verifier
```

Run the same task through each configuration.

Compare:

```text
Success
Failures
Recovery
Latency
Token usage
Number of deliberations
Decision reversals
False approvals
Context size
```

The system becomes a laboratory for agent governance.

---

# 29. The System Should Make Invisible Dynamics Visible

The ultimate dashboard should not merely show:

```text
Agent A: active
Agent B: active
Agent C: completed
```

It should show:

```text
WHY did Agent B disagree?

WHAT evidence changed the leader's decision?

WHO predicted the failure?

WHICH proposal was discarded?

WHICH minority opinion became correct?

WHAT information entered the leader's context?

WHAT information was compressed?

WHY did the system retry?

WHAT changed between attempt 1 and attempt 2?
```

These are the important observability questions.

---

# 30. The Society Should Learn From Its History

The system should not blindly repeat previous mistakes.

Historical traces can inform future routing.

Example:

```text
Previous task:
    database migration

Agent A:
    failed twice

Agent B:
    succeeded four times

Future task:
    database migration

Routing recommendation:
    Agent B → primary specialist
    Agent A → secondary reviewer
```

But preserve the evidence and allow human override.

Do not permanently label an agent as "bad."

Models change.

Tasks differ.

Evidence must remain contextual.

---

# 31. Human Operator

The human should remain able to inspect and override the society.

The UI should allow:

```text
Pause
Resume
Approve
Reject
Override
Reassign leader
Reassign role
Replay
Rollback
Inspect trace
Inspect memory
Inspect policy
Inspect decision provenance
```

The human should be able to enter the simulation without destroying the historical trace.

---

# 32. Replayability

A completed society run should be replayable.

Given:

```text
Task
Agent configuration
Model configuration
Prompts
Context
Tool calls
Policies
Events
Decisions
Environment state
```

OpenMesh should attempt to reconstruct the decision process.

Exact deterministic reproduction may not always be possible with stochastic external models.

Therefore distinguish:

```text
Exact replay
```

from:

```text
Trace reconstruction
```

Never falsely claim deterministic replay when the underlying model is stochastic.

---

# 33. Counterfactual Simulation

A future capability:

After a failure, allow the user to ask:

> What would have happened if the leader had selected Proposal B instead?

OpenMesh can replay or simulate the alternative branch.

Conceptually:

```text
                 Decision
                    │
             ┌──────┴──────┐
             A             B
             │             │
          FAILED        SUCCESS
```

This creates a decision-tree visualization.

Counterfactual results must be clearly marked as simulated rather than historical facts.

---

# 34. Society Health

OpenMesh should eventually provide a high-level system state.

Not a single "AI intelligence score."

Instead:

```text
Society Health

Deliberation diversity
Decision stability
Failure recovery
Verification coverage
Context efficiency
Policy compliance
Agent availability
Authority conflicts
Repeated failures
Unresolved disagreements
```

These are operational indicators.

Avoid reducing the entire society to one simplistic score.

---

# 35. Failure Patterns

OpenMesh should automatically detect recurring patterns such as:

```text
Repeated hallucinated APIs

Repeated context overflow

Repeated leader overrule of successful critics

Repeated execution without verification

Repeated retries without changing assumptions

Repeated disagreement between specific agents

Repeated failure after context compression

Repeated loss of minority objections
```

These should appear as explainable patterns linked to actual traces.

---

# 36. The Most Important Future Loop

The eventual OpenMesh loop should look like:

```text
OBSERVE
   ↓
THINK
   ↓
DISAGREE
   ↓
CRITIQUE
   ↓
DECIDE
   ↓
AUTHORIZE
   ↓
EXECUTE
   ↓
VERIFY
   ↓
OBSERVE RESULT
   ↓
LEARN
   ↓
RETHINK IF NECESSARY
   ↓
DECIDE AGAIN
```

This is the heart of the architecture.

---

# 37. Do Not Build Everything Immediately

This document is intentionally broader than the current implementation.

Do not attempt to implement every concept at once.

The implementation should evolve incrementally.

Suggested progression:

```text
Phase 1
Existing OpenMesh observability

        ↓

Phase 2
Multi-agent event tracing

        ↓

Phase 3
Roles + leader

        ↓

Phase 4
Decision provenance

        ↓

Phase 5
Failure-triggered rethinking

        ↓

Phase 6
Agent characteristics/history

        ↓

Phase 7
Governance graph

        ↓

Phase 8
Agentopedia

        ↓

Phase 9
Society simulation

        ↓

Phase 10
Counterfactual simulation
```

Do not break working OpenMesh functionality merely to reach a future phase.

---

# 38. Architectural Principle

The most important principle for future OpenMesh development:

> **OpenMesh should not attempt to make every agent identical. It should make differences between agents observable, governable, and useful.**

A weak agent may discover something a strong agent missed.

A critic may correctly predict a leader's failure.

A minority proposal may become the correct solution.

A leader may make an incorrect decision.

A verifier may invalidate the leader.

A failure may cause the society to discover a better approach.

All of these events are valuable information.

The system should preserve them.

---

# 39. Final Vision

OpenMesh should eventually feel less like:

```text
AI → API → response
```

and more like:

```text
                         OPENMESH SOCIETY

                              HUMAN
                                │
                                ▼
                             MISSION
                                │
                                ▼
                         ┌──────────────┐
                         │   SOCIETY    │
                         └──────┬───────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                 │
           THINKERS          CRITICS          SPECIALISTS
              │                 │                 │
              └─────────────────┼─────────────────┘
                                │
                          DELIBERATION
                                │
                                ▼
                             LEADER
                                │
                            AUTHORITY
                                │
                                ▼
                            EXECUTOR
                                │
                             ACTION
                                │
                                ▼
                           ENVIRONMENT
                                │
                             RESULT
                                │
                                ▼
                            VERIFIER
                                │
                    ┌───────────┴───────────┐
                    │                       │
                 SUCCESS                  FAILURE
                    │                       │
                    ▼                       ▼
                  AUDIT                 RE THINK
                                            │
                                            ▼
                                        SOCIETY
```

The civilization should be observable at every stage.

OpenMesh should make it possible to see not only **what an AI did**, but:

> **what the society believed, who disagreed, who influenced the decision, what authority was exercised, what evidence changed the decision, what failed, and how the society adapted afterward.**

That is the long-term direction.

Do not treat this as a requirement to implement immediately.

Treat it as the **north star for OpenMesh architecture**.

Every future feature should be evaluated against one question:

> **Does this help us understand, govern, verify, or improve the behavior of a heterogeneous society of AI agents?**
