# src/db/models/common.py
import enum

class GenderEnum(str, enum.Enum):
    male = "male"
    female = "female"
