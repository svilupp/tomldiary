from pydantic import BaseModel

from tomldiary.models import PreferenceItem


class MyPrefTable(BaseModel):
    """
    like    : Things the user actively enjoys (foods, hobbies, styles).
    dislike : Things the user avoids or dislikes.
    allergy : Substances that trigger allergic reactions.
    habit   : Stable routines (e.g., drinks coffee every morning).
    about   : Biographical facts unlikely to change (city, profession).
    """

    like: dict[str, PreferenceItem] = {}
    dislike: dict[str, PreferenceItem] = {}
    allergy: dict[str, PreferenceItem] = {}
    habit: dict[str, PreferenceItem] = {}
    about: dict[str, PreferenceItem] = {}
