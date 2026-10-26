"""
Module Manifest Specification and Pydantic Validator.
"""

from typing import Any

from pydantic import BaseModel, Field


class DependencySpec(BaseModel):
    module: str
    min_version: str = "1.0.0"


class EventConsumerSpec(BaseModel):
    event: str
    handler: str


class UINavEntry(BaseModel):
    id: str
    title: str
    path: str
    icon: str
    order: int = 100
    required_permission: str | None = None


class UISpec(BaseModel):
    nav_entries: list[UINavEntry] = Field(default_factory=list)


class ModuleManifest(BaseModel):
    """
    Formal specification of an Elixir EIM Module.
    Every module must include a compliant module.yaml.
    """

    schema_version: str = "1.0.0"
    name: str
    version: str
    title: str
    description: str
    dependencies: list[DependencySpec] = Field(default_factory=list)
    required_permissions: list[str] = Field(default_factory=list)
    events_published: list[str] = Field(default_factory=list)
    events_consumed: list[EventConsumerSpec] = Field(default_factory=list)
    config_schema: dict[str, Any] = Field(default_factory=dict)
    feature_flag_key: str | None = None
    ui: UISpec = Field(default_factory=UISpec)
