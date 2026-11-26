from enum import StrEnum


class BagState(StrEnum):
    SEALED = "sealed"
    RESERVED = "reserved"
    IN_TRANSIT = "in_transit"
    RELEASED = "released"


class ClaimState(StrEnum):
    VERIFIED = "verified"
    RELEASED = "released"


class TransferState(StrEnum):
    DISPATCHED = "dispatched"
    RECEIVED = "received"


class SearchState(StrEnum):
    QUEUED = "queued"
    RANKED = "ranked"
    FAILED = "failed"


class Role(StrEnum):
    CLERK = "clerk"
    DISPATCHER = "dispatcher"
    OBSERVER = "observer"


class Category(StrEnum):
    BAG = "包袋"
    CLOTHING = "衣物"
    DIGITAL = "数码"
    DOCUMENT = "票证"
    ACCESSORY = "配件"
