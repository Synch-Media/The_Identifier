from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Identity(StrictModel):
    name: str | None = Field(default=None, max_length=500)
    brand: str | None = Field(default=None, max_length=300)
    product_name: str | None = Field(default=None, max_length=300)
    style_accent: str | None = Field(default=None, max_length=300)
    item_type: str | None = Field(default=None, max_length=300)


class Recognition(Identity):
    status: Literal['Resolved', 'Needs Evidence', 'Unresolved']
    candidate: str | None = None
    evidence: str = ''
    missing_evidence: str = ''
    next_action: str = ''
    reason_unresolved: str = ''
    missing_optional_information: str = ''
    sources: str = ''


class KnownInfo(StrictModel):
    brand: str = Field(default='', max_length=300)
    product_name: str = Field(default='', max_length=300)
    identifiers: str = Field(default='', max_length=500)
    item_type: str = Field(default='', max_length=300)
    other_information: str = Field(default='', max_length=3000)


class RunInput(StrictModel):
    known: KnownInfo = Field(default_factory=KnownInfo)
    no_more_information: bool = False


class DecisionInput(StrictModel):
    action: Literal['confirmed', 'corrected', 'rejected', 'accepted general identity']
    identity: Identity | None = None
