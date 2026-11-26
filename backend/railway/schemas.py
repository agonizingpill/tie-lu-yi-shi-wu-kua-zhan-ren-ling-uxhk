from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

from railway.enums import Category


def constrained(min_length, max_length):
    return StringConstraints(strip_whitespace=True, min_length=min_length, max_length=max_length)


Seal = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Z0-9][A-Z0-9-]{3,24}$")]
Train = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Z][0-9]{2,6}$")]
Station = Annotated[str, StringConstraints(pattern=r"^[A-Z]{2,6}$")]
Proof = Annotated[str, constrained(3, 80)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(Input):
    email: Annotated[str, constrained(5, 100)]
    password: Annotated[str, constrained(5, 128)]


class PublicClue(Input):
    category: Category
    color: Annotated[str, constrained(1, 32)]
    description: Annotated[str, constrained(2, 160)]


class NewSeal(PublicClue):
    seal_id: Seal
    train_no: Train
    found_on: date
    private_mark: Proof

    @field_validator("found_on")
    @classmethod
    def not_future(cls, value: date):
        if value > date.today():
            raise ValueError("拾获日期不能晚于今天")
        return value


class SearchClue(PublicClue):
    travel_on: date
    train_no: Train | None = None


class ClaimProof(Input):
    search_id: int
    seal_id: Seal
    answer: Proof


class DispatchRequest(Input):
    claim_id: int
    carrier_train: Train


class ArrivalReceipt(Input):
    scanned_seal: Seal


class ReleaseReceipt(Input):
    scanned_seal: Seal
