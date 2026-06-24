# AI Agent Mode for Interactive Resume Tailoring

## Motivation

The current resume tailoring pipeline is mostly automatic: it extracts the resume and job description, optionally retrieves RAG context, builds a knowledge graph, and generates a tailored resume. This is efficient, but it has one important limitation: the system can only use information that already exists in the uploaded resume or retrieved evidence. If the original resume is missing dates, diploma names, project links, exact implemented features, collaboration context, or measurable outcomes, the LLM must either produce weaker bullet points or risk hallucinating.

An AI agent mode can address this limitation by adding a human-in-the-loop step before final resume generation. During the tailoring process, a chat interface opens directly on the generation page. The agent proactively asks the user short, targeted questions, collects missing or useful evidence, and then passes the user-provided answers into the resume generation step as additional grounded context.

The goal is not to make the user manually rewrite the resume. The goal is to ask only the highest-value questions that help the system generate stronger, more truthful, job-aligned content.

## Proposed User Experience

AI agent mode would be an optional mode enabled from the settings panel before generation. When enabled, the normal generation page still shows the pipeline steps, but before final resume tailoring begins, an embedded chat panel opens.

The chat panel should support:

- one question at a time,
- a normal text answer,
- quick actions: `Skip`, `No`, `I don't want to answer`,
- a global `Skip all questions` action,
- a progress indicator such as `Question 3 of 8`,
- a final message thanking the user before generation continues.

The agent should not ask unlimited questions. A practical upper bound should be used, for example 8-12 total questions, with prioritization based on expected impact.

## Agent Flow

### Stage 1: Missing Information Collection

The first stage focuses on missing structured information in the parsed resume. These questions improve resume completeness and PDF quality, but they should remain low-pressure.

Examples:

- Missing start or end dates for work experience, projects, or education.
- Missing diploma or degree names.
- Missing university department/program names.
- Missing project links, GitHub links, demos, publications, or portfolio URLs.
- Missing certification issuer or verification link.
- Missing location only when location is clearly appropriate and not risky to infer.

Example questions:

- "What was the start and end date for your OpenGL rendering project?"
- "What is the exact diploma or degree name for your Tsinghua University program?"
- "Do you have a GitHub, demo, or project link for this project?"

The user can answer, say they do not have the information, refuse to answer, skip one question, or skip all remaining questions.

### Stage 2: Evidence Collection for Strong Rewrites

The second stage focuses on bullet points that the system is about to rewrite. The agent should identify non-achievement bullet points from work experience and projects that are strongly related to the job description, then ask for missing implementation details that would support more advanced bullet points.

This stage should not ask about preserved achievement/funding/award bullets, because those should remain unchanged. It should focus on bullets where richer evidence would help generate stronger XYZ-style statements.

The agent should ask about:

- the direct feature implemented,
- the technical decision or implementation approach,
- the user-facing or business outcome,
- measurable impact if available,
- team/collaboration context,
- performance, usability, reliability, or maintainability improvements,
- constraints, ownership, or communication with other people.

Example questions:

- "For the frontend project you mentioned, what exact interface or feature did you build?"
- "Did this work improve usability, performance, loading speed, reliability, or development speed in any measurable way?"
- "Was this project built independently or with a team? If with a team, what was your role?"
- "For this project, did you communicate with users, teammates, designers, or stakeholders?"

The agent should avoid leading the user into fabrication. For example, it should not ask, "What metric did you improve?" in a way that pressures the user to invent one. Better wording is: "Was there any measurable result, even approximate? If not, you can say no."

## Agent Question Selection

The agent should not ask every possible question. It should rank candidate questions by usefulness.

Possible prioritization rules:

1. Ask missing required structural fields first if they affect resume rendering or credibility.
2. Prioritize work/project entries with high job relevance.
3. Prioritize bullet points that are short, vague, or generic but related to the job.
4. Ask for metrics only when the original bullet implies an outcome but lacks detail.
5. Avoid questions about facts that are already clear in the resume.
6. Stop early if enough useful evidence has been collected.

This can be implemented as a question-planning step after resume extraction, job extraction, RAG, and knowledge graph construction, but before resume generation.

## Pipeline Integration

The proposed pipeline becomes:

1. Upload resume and job description.
2. Extract structured resume JSON.
3. Extract structured job details.
4. Retrieve RAG context if enabled.
5. Build knowledge graph if enabled.
6. If AI agent mode is enabled, generate a prioritized question plan.
7. Open chat UI and ask selected questions.
8. Store user answers as structured evidence.
9. Pass original resume, job details, RAG context, knowledge graph, and agent-collected evidence into the tailoring step.
10. Generate the tailored resume.
11. Render PDF and compute metrics.

The important design constraint is that agent-provided answers should be treated as additional evidence, not as free-form instructions. The tailoring prompt should explicitly state that the model may use user answers only as factual support for related resume entries.

## Suggested Data Model

A possible structure for agent-collected evidence:

```json
{
  "agent_mode": true,
  "answers": [
    {
      "question_id": "work_0_dates",
      "target_section": "work_experience_section",
      "target_item_key": "company::role",
      "target_field": "from_date/to_date",
      "question": "What were the start and end dates for this role?",
      "answer": "June 2023 - August 2023",
      "status": "answered"
    },
    {
      "question_id": "project_1_feature",
      "target_section": "projects_section",
      "target_item_key": "project_name",
      "target_field": "description",
      "question": "What exact frontend feature did you implement?",
      "answer": "Built an interactive dashboard with filtering and detail views.",
      "status": "answered"
    },
    {
      "question_id": "project_1_metric",
      "target_section": "projects_section",
      "target_item_key": "project_name",
      "target_field": "description",
      "question": "Was there any measurable result?",
      "answer": null,
      "status": "skipped"
    }
  ]
}
```

Statuses could include:

- `answered`
- `skipped`
- `declined`
- `not_available`
- `skip_all`

This makes the evidence auditable and allows the system to distinguish between "missing because not asked" and "missing because the user declined or does not know."

## Prompting Strategy

The agent should use a different prompt from the resume generator. The agent prompt should focus on asking concise, factual, low-pressure questions.

Important rules:

- Ask one question at a time.
- Explain the target resume entry when needed.
- Do not ask for sensitive personal information unless necessary.
- Do not pressure the user to invent metrics.
- Accept "no", "I don't know", "I don't want to answer", and skipped questions.
- Prefer concrete evidence over broad self-promotion.
- Stop when the expected value of further questions is low.

The resume generation prompt should then include the collected answers in a separate section, for example:

```text
<USER_AGENT_EVIDENCE>
Use this information only as factual evidence for the corresponding resume entries.
Do not apply an answer to unrelated entries.
Do not invent missing metrics when the user skipped or declined a metric question.
...
</USER_AGENT_EVIDENCE>
```

## Research Hypothesis

AI agent mode should improve resume quality compared to fully automatic tailoring because it reduces missing evidence and helps the model generate more concrete, truthful, job-aligned bullet points.

Possible hypothesis:

> Human-in-the-loop agentic evidence collection improves job alignment and structural quality while reducing hallucination risk compared to fully automatic resume tailoring.

## Evaluation Plan

AI agent mode can be evaluated against the existing automatic pipeline.

Experimental conditions:

1. Prompt-only tailoring.
2. RAG + knowledge graph tailoring.
3. RAG + knowledge graph + AI agent mode.

Metrics:

- Job alignment.
- Content preservation.
- Structural validity.
- Hallucination rate.
- Number of unsupported claims.
- Number of concrete feature/action/outcome bullet points.
- User-perceived trust.
- User-perceived effort.
- Time to final resume.
- Skip rate per question type.

The key tradeoff is quality versus user effort. Agent mode should not be considered better only because it asks more questions. It is better if it asks a small number of useful questions and produces a resume that users trust more.

## Expected Benefits

AI agent mode could improve:

- factual grounding,
- quality of rewritten bullet points,
- completeness of missing dates, links, and education details,
- user trust,
- user control,
- transparency of where new information came from,
- support for conservative tailoring without losing relevance.

It also fits the broader research direction of HCI-based resume tailoring, where users selectively contribute information instead of letting the model rewrite everything blindly.

## Risks and Mitigations

The main risk is user fatigue. If the agent asks too many questions, the system becomes slower than manual editing. This can be mitigated by limiting total questions, ranking them by usefulness, and providing `Skip all`.

Another risk is answer misuse. A detail provided for one project could accidentally influence another project. This should be mitigated by storing answers with explicit section and item references.

A third risk is fabrication pressure. Asking for metrics can make users feel that they should invent numbers. The agent should always allow "no metric" and should phrase such questions carefully.

Finally, the agent could ask obvious or annoying questions if extraction is already complete. The question planner should suppress low-value questions and avoid asking about fields already present.

## Implementation Notes

On the frontend, the chat can be embedded into the existing generation page before the resume generation step. The backend can stream an event such as:

```json
{"type": "agent_questions_start", "data": {"question_count": 8}}
```

Then the frontend can display each question and send answers back through a new endpoint or a websocket. A simple first implementation could use REST endpoints:

- `POST /api/agent/question-plan`
- `POST /api/agent/answer`
- `POST /api/tailor/continue`

For a smoother implementation, websocket or server-sent events with client responses would be better, but this is more complex.

The minimal viable version can be simpler:

1. Backend generates all planned questions.
2. Frontend displays them one by one.
3. User answers/skips.
4. Frontend sends all answers back.
5. Backend starts final generation.

This avoids complex bidirectional streaming in the first prototype.

## Conclusion

AI agent mode is a promising extension of the current resume tailoring system. It directly addresses one of the biggest weaknesses of fully automatic LLM tailoring: missing evidence. By asking targeted, skippable questions before generation, the system can produce more specific and trustworthy resumes while preserving user control. The most important design challenge is keeping the interaction short, respectful, and evidence-focused.
