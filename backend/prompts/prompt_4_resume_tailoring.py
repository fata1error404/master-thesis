PERSON_DESCRIPTION = """
You are going to write the applicant's person self-description / resume summary for a target job.

The output must be a single JSON field named "summary".

Decision policy:
1. Always generate a fresh person description for the target job.
2. If the original person description exists, use it only as a reference for the author's style, tone,
   point of view, sentence rhythm, and level of formality. Do not copy it unchanged.
3. If the original person description does not exist, generate a two-sentence person description aligned with the target job.

Truthfulness:
- Do not invent employers, degrees, dates, awards, certifications, links, exact metrics, seniority, or technologies.
- Every factual claim must be supported by the resume evidence supplied to you.
- Do not list skills or technologies in the person description.
- You may imply supported domains, interests, projects, education, and work evidence that are relevant to the target job.
- If the resume evidence is thin, keep the summary general rather than fabricating details.
- Mention the person's current position, such as "Master's student", if and only if the original person description explicitly contains that current position.

Style:
- Clear, polished, human resume prose.
- No bullet points.
- No first-person pronouns unless the original person description uses them.
- Use exactly two concise sentences.
- The first sentence should express target-role interest, for example a keen interest in building interactive, user-friendly interfaces.
- The second sentence should add human working qualities such as communication, collaboration, ownership, problem-solving, attention to detail, or learning mindset.
- Avoid phrases like "experience across", "skilled in", "proficient in", "technical skills", "tech stack", or comma-separated skill lists.

<original_person_description>
    {original_summary}
</original_person_description>

<resume_evidence>
    {resume_evidence}
</resume_evidence>

<job_description>
    {job_description}
</job_description>
"""


WORK_EXPERIENCE = """
You are going to write a JSON resume section of "Work Experience" for an applicant applying for job posts.

Step to follow:
1. Analyze my Work details to match job requirements.
2. Create a JSON resume section that highlights strongest matches
3. Optimize JSON section for clarity and relevance to the job description.

Instructions:
1. Focus: Prioritize work experiences that are most aligned with the job description.
2. Content:
  2.1. Preserve all achievement, award, funding, competition, hackathon, prize, ranking, and grant bullets verbatim. Do not rewrite, expand, paraphrase, reorder internally, or add job-description keywords to these achievement facts.
  2.2. For work experiences strongly related to the job description, ensure there are at least 2 non-achievement bullet points in addition to any preserved achievement bullets.
  2.3. Rewrite these related non-achievement bullets in a richer way. Firstly, you must use XYZ formula everywhere: did X, using Y, to improve Z (metric). Secondly, it must not sound general: describe concrete implemented feature or technical decision grounded (if possible) in the original work details (if they are weak, generate a fake one).
  2.4. For work experiences weakly related to the job description, keep bullets concise and avoid aggressive rewriting.
3. Style:
  3.1. Clarity: Clear expression trumps impressiveness.
  3.2. Voice: Use active voice whenever possible.
  3.3. Proofreading: Ensure impeccable spelling and grammar.

<work_experience_section>
    {section_data}
</work_experience_section>

<job_description>
    {job_description}
</job_description>

<example>
    "work_experience_section": [
        {{
        "role": "Software Engineer",
        "company": "Winjit Technologies",
        "location": "Pune, India"
        "from_date": "Jan 2020",
        "to_date": "Jun 2022",
        "description": [
            "Engineered 10+ RESTful APIs Architecture and Distributed services; Designed 30+ low-latency responsive UI/UX application features with high-quality web architecture; Managed and optimized large-scale Databases. (Systems Design)",  
            "Initiated and Designed a standardized solution for dynamic forms generation, with customizable CSS capabilities feature, which reduces development time by 8x; Led and collaborated with a 12 member cross-functional team. (Idea Generation)"  
            and so on ...
        ]
        }},
        {{
        "role": "Research Intern",
        "company": "IMATMI, Robbinsville",
        "location": "New Jersey (Remote)"
        "from_date": "Mar 2019",
        "to_date": "Aug 2019",
        "description": [
            "Conducted research and developed a range of ML and statistical models to design analytical tools and streamline HR processes, optimizing talent management systems for increased efficiency.",
            "Created 'goals and action plan generation' tool for employees, considering their weaknesses to facilitate professional growth.",
            and so on ...
        ]
        }}
    ],
</example>
"""


EDUCATION = """
You are going to write a JSON resume section of "Education" for an applicant applying for job posts.

Step to follow:
1. Analyze my education details to match job requirements.
2. Create a JSON resume section that highlights strongest matches
3. Optimize JSON section for clarity and relevance to the job description.

Instructions:
- Maintain truthfulness and objectivity in listing experience.
- Prioritize specificity - with respect to job - over generality.
- Proofread and Correct spelling and grammar errors.
- Aim for clear expression over impressiveness.
- Prefer active voice over passive voice.

<education_section>
    {section_data}
</education_section>

<job_description>
    {job_description}
</job_description>

<example>
    "education_section": [
    {{
        "degree": "Masters of Science - Computer Science (Thesis)",
        "university": "Arizona State University, Tempe, USA",
        "from_date": "Aug 2023",
        "to_date": "May 2025",
        "grade": "3.8/4",
        "coursework": [
        "Operational Deep Learning",
        "Software verification, Validation and Testing",
        "Social Media Mining",
        [and So on ...]
        ]
    }}
    [and So on ...]
    ],
</example>
"""


SKILLS = """
You are going to write a JSON resume section of "Skills" for an applicant applying for job posts.

Step to follow:
1. Analyze my Skills details to match job requirements.
2. Create a JSON resume section that highlights strongest matches.
3. Optimize JSON section for clarity and relevance to the job description.

Instructions:
- Specificity: Prioritize relevance to the specific job over general achievements.
- Proofreading: Ensure impeccable spelling and grammar.

<skills_section>
    {section_data}
</skills_section>

<job_description>
    {job_description}
</job_description>

<example>
    "skills_section": [
        {{
        "name": "Programming Languages",
        "skills": ["Python", "JavaScript", "C#", and so on ...]
        }},
        {{
        "name": "Cloud and DevOps",
        "skills": [ "Azure", "AWS", and so on ... ]
        }},
        and so on ...
    ]
</example>
"""


PROJECTS = """
You are going to write a JSON resume section of "Project Experience" for an applicant applying for job posts.

Step to follow:
1. Analyze my project details to match job requirements.
2. Create a JSON resume section that highlights strongest matches
3. Optimize JSON section for clarity and relevance to the job description.

Instructions:
1. Focus: Craft three highly relevant project experiences aligned with the job description.
2. Content:
  2.1. Bullet points: 3 per experience, closely mirroring job requirements.
  2.2. Impact: Quantify each bullet point for measurable results.
  2.3. Storytelling: Utilize STAR methodology (Situation, Task, Action, Result) implicitly within each bullet point.
  2.4. Action Verbs: Showcase soft skills with strong, active verbs.
  2.5. Honesty: Prioritize truthfulness and objective language.
  2.6. Structure: Each bullet point follows "Did X by doing Y, achieved Z" format.
  2.7. Specificity: Prioritize relevance to the specific job over general achievements.
3. Style:
  3.1. Clarity: Clear expression trumps impressiveness.
  3.2. Voice: Use active voice whenever possible.
  3.3. Proofreading: Ensure impeccable spelling and grammar.

<projects_section>
    {section_data}
</projects_section>

<job_description>
    {job_description}
</job_description>

<example>
    "projects_section": [
        {{
        "name": "Search Engine for All file types - Sunhack Hackathon - Meta & Amazon Sponsored",
        "type": "Hackathon",
        "link": "https://devpost.com/software/team-soul-1fjgwo",
        "from_date": "Nov 2023",
        "to_date": "Nov 2023",
        "description": [
            "1st runner up prize in crafted AI persona, to explore LLM's subtle contextual understanding and create innovative collaborations between humans and machines.",
            "Devised a TabNet Classifier Model having 98.7% accuracy in detecting forest fire through IoT sensor data, deployed on AWS and edge devices 'Silvanet Wildfire Sensors' using technologies TinyML, Docker, Redis, and celery.",
            [and So on ...]
        ]
        }}
        [and So on ...]
    ]
</example>
"""


CERTIFICATIONS = """
You are going to write a JSON resume section of "Certifications" for an applicant applying for job posts.

Step to follow:
1. Analyze my certification details to match job requirements.
2. Create a JSON resume section that highlights strongest matches
3. Optimize JSON section for clarity and relevance to the job description.

Instructions:
1. Focus: Include relevant certifications aligned with the job description.
2. Proofreading: Ensure impeccable spelling and grammar.

<certifications_section>
    {section_data}
</certifications_section>

<job_description>
    {job_description}
</job_description>

<example>
    "certifications_section": [
        {{
        "name": "Deep Learning Specialization",
        "by": "DeepLearning.AI, Coursera Inc.",
        "link": "https://www.coursera.org/account/accomplishments/specialization/G3WPNWRYX628"
        }},
        {{
        "name": "Server-side Backend Development",
        "by": "The Hong Kong University of Science and Technology.",
        "link": "https://www.coursera.org/account/accomplishments/verify/TYMQX23D4HRQ"
        }}
        ...
    ],
</example>
"""


ACHIEVEMENTS = """
You are going to write a JSON resume section of "Achievements" for an applicant applying for job posts.

Step to follow:
1. Analyze my achievements details to match job requirements.
2. Create a JSON resume section that highlights strongest matches
3. Optimize JSON section for clarity and relevance to the job description.

Instructions:
1. Focus: Craft relevant achievements aligned with the job description.
2. Honesty: Prioritize truthfulness and objective language.
3. Specificity: Prioritize relevance to the specific job over general achievements.
4. Style:
  4.1. Voice: Use active voice whenever possible.
  4.2. Proofreading: Ensure impeccable spelling and grammar.

<achievements_section>
    {section_data}
</achievements_section>

<job_description>
    {job_description}
</job_description>

<example>
    "achievements_section": [
        "Won E-yantra Robotics Competition 2018 - IITB.",
        "1st prize in “Prompt Engineering Hackathon 2023 for Humanities”",
        "Received the 'Extra Miller - 2021' award at Winjit Technologies for outstanding performance.",
        [and So on ...]
    ]
</example>
"""
