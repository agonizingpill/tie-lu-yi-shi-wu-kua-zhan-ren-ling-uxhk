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
    ticket_id: int | None = None
    verification_id: int | None = None
    call_id: int | None = None
    number: int | None = None
    verification_no: int | str | None = None
    ticket_no: int | str | None = None
    call_no: int | str | None = None
    idempotency_key: str | int | None = None
    idempotency_token: str | int | None = None
    request_id: str | int | None = None
    request_token: str | int | None = None
    client_token: str | int | None = None
    nonce: str | int | None = None
    key: str | int | None = None


class CallNumberRequest(Input):
    model_config = ConfigDict(extra="allow")

    search_id: int | None = None
    id: int | None = None
    seal_id: str | None = None
    search_ids: list[int] | None = None
    station_code: str | None = None
    station: str | None = None
    all_eligible: bool | None = True
    allocate_all: bool | None = None


class VerifyNumberRequest(Input):
    model_config = ConfigDict(extra="allow")

    id: int | None = None
    verification_id: int | None = None
    ticket_id: int | None = None
    call_id: int | None = None
    number: int | None = None
    verification_no: int | str | None = None
    ticket_no: int | str | None = None
    call_no: int | str | None = None
    answer: str | None = None
    proof: str | None = None
    private_mark: str | None = None
    code: str | None = None
    idempotency_key: str | int | None = None
    idempotency_token: str | int | None = None
    request_id: str | int | None = None
    request_token: str | int | None = None
    client_token: str | int | None = None
    nonce: str | int | None = None
    key: str | int | None = None


class DispatchRequest(Input):
    claim_id: int
    carrier_train: Train


class ArrivalReceipt(Input):
    scanned_seal: Seal


class ReleaseReceipt(Input):
    scanned_seal: Seal
