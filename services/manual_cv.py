"""Turn the "Enter manually" form into CV text.

The result reads like a normal CV, so the same extractors handle typed and
uploaded CVs, and there is only one path through the system.
"""


def build_cv_text(name: str = "", email: str = "", phone: str = "", location: str = "", total_years: float = 0,
                  skills: str = "", work_experience: str = "", education: str = "", other_text: str = "") -> str:
    """Write the form fields out as a labelled CV."""
    header = [f"{label}: {value.strip()}" for label, value in
              (("Name", name), ("Email", email), ("Phone", phone), ("Location", location)) if value.strip()]
    if total_years:
        header.append(f"Total Experience: {total_years:g} years")

    sections = ["\n".join(header)] if header else []
    for heading, body in (("SKILLS", skills), ("WORK EXPERIENCE", work_experience), ("EDUCATION", education)):
        if body.strip():
            sections.append(f"{heading}\n{body.strip()}")
    if other_text.strip():
        sections.append(other_text.strip())
    return "\n\n".join(sections)
