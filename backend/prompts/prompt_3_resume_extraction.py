RESUME_DETAILS_EXTRACTOR = """
<objective>
    Parse a text-formatted resume efficiently and extract diverse applicant's data into a structured JSON format.
</objective>

<input>
    The following text is the applicant's resume in plain text format:

    {resume_text}
</input>

<instructions>
    Follow these steps to extract and structure the resume information:

    1. Analyze Structure:
    - Examine the text-formatted resume to identify key sections (e.g., personal information, education, experience, skills, certifications).
    - Note any unique formatting or organization within the resume.

    2. Extract Information:
    - Systematically parse each section, extracting relevant details.
    - If the resume contains a person self-description, profile, summary, objective, bio, "about me",
      or short introductory paragraph near the candidate name/contact information, extract it into
      the top-level "summary" field.
    - Preserve the author's original wording, tone, and point of view for the "summary" field as much
      as possible; do not convert it into bullet points or scatter it across other sections.
    - If there is no explicit person self-description, set "summary" to null or an empty string.
    - Pay attention to dates, titles, organizations, and descriptions.
    - In education, preserve department/faculty/program names, GPA/grade, honors, thesis titles, scholarships, selective programs, and university ranking/prestige facts exactly when present.
    - Put department/faculty/program names in the education "department" field; do not convert them into a generic degree.
    - Put GPA or grade in the education "grade" field, and put ranking/prestige/honors/thesis facts in education "highlights".
    - Extract project descriptions from any bullets, short paragraphs, or indented lines that appear under a project name.
    - Do not leave project descriptions empty if the resume text contains evidence below or near that project title.
    - Preserve project names, links, and descriptions exactly enough that they remain factually grounded.

    3. Handle Variations:
    - Account for different resume styles, formats, and section orders.
    - Adapt the extraction process to accurately capture data from various layouts.

    5. Optimize Output:
    - Handle missing or incomplete information appropriately (use null values or empty arrays/objects as needed).
    - Standardize date formats, if applicable.
    - Never use "Unknown", "N/A", "Not specified", or similar placeholder strings.
    - For missing dates or locations, use an empty string.
    - For work experience location, extract a value only when the resume explicitly states a location for that specific work entry.
    - Do not infer work locations from education, contact information, current university, candidate address, or surrounding document context.
    - If multiple unrelated work entries would receive the same inferred location, leave their location fields empty instead.

    6. Validate:
    - Review the extracted data for consistency and completeness.
    - Ensure all required fields are populated if the information is available in the resume.
    - Check that GPA/grade and strong education facts did not disappear when present in the resume text.
    - Check that no work experience location was guessed.
    - Check that no project with visible bullet text lost its description.
</instructions>
"""
