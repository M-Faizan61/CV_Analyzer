"""Small builders that keep the tests short."""
from models.schemas import Requirement
from services.pipeline import CvInput


def skill(name, importance="mandatory", requirement_id="R1", **values):
    return Requirement(id=requirement_id, text=f"{name} needed", importance=importance, kind="skill", skills=name, **values)


def typed_cv(text, name="candidate.txt"):
    return CvInput(name=name, source="Manual entry", text=text)
