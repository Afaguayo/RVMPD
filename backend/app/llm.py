"""Optional language-model layer: rewrites the local report from the same aggregated numbers."""
import json
import logging
import os
from typing import Literal

import anthropic
from pydantic import BaseModel, Field

log = logging.getLogger("vitalis.llm")

DEFAULT_MODEL = "claude-opus-5-5"
TIMEOUT_S = 20.0
SYSTEM = """You are the on-board health assistant for an astronaut who is not a doctor. You provide decision \
support only, never a diagnosis: always say "possible", never state that the astronaut has a condition.
You receive aggregated statistics for a recent time window and the findings of a local rule engine. Ground every \
statement in the supplied numbers, quote them in the evidence, and never invent measurements or conditions the \
numbers do not support. A vital marked usable=false came from an untrusted sensor: report it as an equipment \
problem and never use it as evidence for a body condition. If nothing is unusual, return no findings and say so \
in the summary. Use plain words and keep every item short."""


class Finding(BaseModel):
    condition: str
    likelihood: Literal["low", "medium", "high"]
    evidence: list[str] = Field(min_length=1)
    action: str


class ModelReport(BaseModel):
    summary: str
    findings: list[Finding] = Field(max_length=5)
    facts: list[str] = Field(min_length=2, max_length=6)


def make_client():
    """Return (client, model id), or None when no model is configured. Credentials come from the environment only."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        client = anthropic.Anthropic(timeout=TIMEOUT_S, max_retries=0)
        return client, os.environ.get("VITALIS_MODEL", DEFAULT_MODEL)
    if os.environ.get("VITALIS_USE_BEDROCK") == "1":
        region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
        client = anthropic.AnthropicBedrockMantle(aws_region=region, timeout=TIMEOUT_S, max_retries=0)
        return client, os.environ.get("VITALIS_MODEL", f"anthropic.{DEFAULT_MODEL}")
    return None


def refine(stats, local):
    """Return the model's report, or `local` unchanged if the model is missing, slow, failing or invalid."""
    try:
        configured = make_client()
        if configured is None:
            return local
        client, model = configured
        reply = client.messages.parse(
            model=model, max_tokens=4000, system=SYSTEM,
            messages=[{"role": "user", "content": json.dumps(
                {"statistics": stats, "local_findings": local["findings"]}, separators=(",", ":"))}],
            output_config={"effort": "low"}, output_format=ModelReport)
        report = reply.parsed_output
        if report is None:
            return local
        return {**local, **report.model_dump(), "engine": "llm", "model": model}
    except Exception as e:  # the contract: a model failure never becomes an API error
        log.warning("Language model unavailable, using the local report (%s)", type(e).__name__)
        return local
