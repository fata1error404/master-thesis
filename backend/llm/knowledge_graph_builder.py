from schemas.knowledge_graph import KnowledgeGraph, KGNode, KGEdge
from schemas.job_details_schema import JobDetails
from schemas.resume_schema import Resume


def build_knowledge_graph(job: JobDetails, resume: Resume) -> KnowledgeGraph:
    nodes = []
    edges = []

    # -----------------------
    # JOB NODE
    # -----------------------
    job_id = "job_0"
    nodes.append(KGNode(
        id=job_id,
        type="job",
        label=job.job_title,
        meta={"company": job.company_name}
    ))

    # -----------------------
    # KEYWORDS → SKILLS
    # -----------------------
    for i, kw in enumerate(job.keywords):
        skill_id = f"skill_job_{i}"
        nodes.append(KGNode(
            id=skill_id,
            type="skill",
            label=kw
        ))

        edges.append(KGEdge(
            source=job_id,
            target=skill_id,
            relation="requires"
        ))

    # -----------------------
    # RESUME SKILLS
    # -----------------------
    for s_i, section in enumerate(resume.skills_section):
        section_id = f"skill_section_{s_i}"

        nodes.append(KGNode(
            id=section_id,
            type="skill",
            label=section.name
        ))

        edges.append(KGEdge(
            source="resume",
            target=section_id,
            relation="has_skill_group"
        ))

        for skill in section.skills:
            skill_id = f"skill_{section_id}_{skill}"

            nodes.append(KGNode(
                id=skill_id,
                type="skill",
                label=skill
            ))

            edges.append(KGEdge(
                source=section_id,
                target=skill_id,
                relation="contains"
            ))

    # -----------------------
    # EXPERIENCE → SKILLS (light linking)
    # -----------------------
    for i, exp in enumerate(resume.work_experience_section):
        exp_id = f"exp_{i}"

        nodes.append(KGNode(
            id=exp_id,
            type="experience",
            label=f"{exp.role} @ {exp.company}"
        ))

        edges.append(KGEdge(
            source="resume",
            target=exp_id,
            relation="has_experience"
        ))

        # soft link keywords
        for kw in job.keywords:
            if kw.lower() in " ".join(exp.description).lower():
                edges.append(KGEdge(
                    source=exp_id,
                    target=f"skill_{kw}",
                    relation="matches"
                ))

    # -----------------------
    # PROJECTS
    # -----------------------
    for i, project in enumerate(resume.projects_section):
        pid = f"project_{i}"

        nodes.append(KGNode(
            id=pid,
            type="project",
            label=project.name
        ))

        edges.append(KGEdge(
            source="resume",
            target=pid,
            relation="has_project"
        ))

    # -----------------------
    # JOB ↔ RESUME LINK
    # -----------------------
    edges.append(KGEdge(
        source="resume",
        target=job_id,
        relation="applied_for"
    ))

    return KnowledgeGraph(nodes=nodes, edges=edges)