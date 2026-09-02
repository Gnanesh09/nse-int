from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel, Field

from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langgraph.graph import (
    StateGraph,
    START,
    END,
)

from .config import settings


# =========================================================
# OUTPUT SCHEMAS
# =========================================================

class ChunkInsight(BaseModel):

    material_facts: list[str] = Field(
        default_factory=list
    )

    key_numbers: list[str] = Field(
        default_factory=list
    )

    management_signals: list[str] = Field(
        default_factory=list
    )

    risks: list[str] = Field(
        default_factory=list
    )

    opportunities: list[str] = Field(
        default_factory=list
    )

    potential_impact: str = ""

    importance_hint: int = Field(
        default=0,
        ge=0,
        le=100,
    )


class FinalAnalysis(BaseModel):

    headline: str

    executive_summary: str

    event_type: str

    importance: int = Field(
        ge=0,
        le=100,
    )

    impact: str

    financial_impact: str

    operational_impact: str

    why_it_matters: str

    key_numbers: list[str] = Field(
        default_factory=list
    )

    key_facts: list[str] = Field(
        default_factory=list
    )

    risks: list[str] = Field(
        default_factory=list
    )

    opportunities: list[str] = Field(
        default_factory=list
    )

    watch_items: list[str] = Field(
        default_factory=list
    )

    management_signals: list[str] = Field(
        default_factory=list
    )

    confidence: int = Field(
        ge=0,
        le=100,
    )


# =========================================================
# LANGGRAPH STATE
# =========================================================

class AnalysisState(
    TypedDict,
    total=False,
):

    announcement: dict

    filing_text: str

    document: str

    chunks: list[str]

    chunk_results: list[dict]

    analysis: dict

    usage: dict


# =========================================================
# PROMPTS
# =========================================================

CHUNK_SYSTEM = """
You are a senior corporate-filings analyst at
SOUTH DECAN CAPITAL.

Analyze one portion of an Indian listed company's
NSE filing.

You are performing evidence extraction.

STRICT RULES:

- Only use facts contained in the supplied text.
- Never invent numbers.
- Never invent dates.
- Never invent counterparties.
- Never invent financial impacts.
- Never make investment recommendations.
- If a fact is not present, do not create it.
- Capture exact disclosed financial figures when present.
- Capture material management statements.
- Capture risks and uncertainties.
- Separate facts from interpretation.

Your job in this stage is not to create the final report.
Extract high-quality evidence that another analyst will
use later.
"""


FINAL_SYSTEM = """
You are the chief corporate-filings analyst for
SOUTH DECAN CAPITAL.

Produce a professional institutional-style research brief
from an NSE corporate announcement and evidence extracted
from its attached filing.

SOURCE HIERARCHY:

1. Attached company filing text
2. NSE announcement details

IMPORTANT:

- Never invent facts.
- Never invent numbers.
- Never invent dates.
- Never invent management statements.
- Never give buy/sell/hold advice.
- Never give a target price.
- Never claim an undisclosed financial impact.
- If unavailable, write "Not disclosed."
- Treat old/contextual information as historical.
- Materiality is not a recommendation.

EVENT TYPES:

results
order
contract
fundraising
acquisition
merger
promoter
management
dividend
buyback
split_bonus
regulatory
litigation
rating
investor_meet
expansion
capex
business_update
esop
other

IMPACT:

positive
negative
mixed
neutral
unclear

MATERIALITY:

0-20   very low
21-40  low
41-60  moderate
61-80  significant
81-100 highly material

Routine ESOP or administrative disclosures should usually
not receive very high materiality unless the filing contains
something genuinely material.

Large orders, acquisitions, fundraising, major regulatory
actions, management changes, major capital expenditure,
IPO/DRHP-related events, and significant business updates
may receive higher materiality when supported by evidence.

Write concise but information-dense output.
"""


# =========================================================
# MODEL
# =========================================================

def create_llm():

    if not settings.groq_api_key:

        raise RuntimeError(
            "GROQ_API_KEY is not configured. "
            "Add it to your .env file."
        )


    return ChatGroq(

        model=settings.groq_model,

        temperature=0,

        max_tokens=(
            settings.groq_max_output_tokens
        ),

        api_key=settings.groq_api_key,

    )


# =========================================================
# USAGE
# =========================================================

def extract_usage(
    message,
) -> dict:

    usage_metadata = (
        getattr(
            message,
            "usage_metadata",
            None,
        )
        or {}
    )

    response_metadata = (
        getattr(
            message,
            "response_metadata",
            None,
        )
        or {}
    )

    input_tokens = int(
        usage_metadata.get(
            "input_tokens",
            response_metadata.get(
                "prompt_tokens",
                0,
            ),
        )
        or 0
    )

    output_tokens = int(
        usage_metadata.get(
            "output_tokens",
            response_metadata.get(
                "completion_tokens",
                0,
            ),
        )
        or 0
    )

    total_tokens = int(
        usage_metadata.get(
            "total_tokens",
            response_metadata.get(
                "total_tokens",
                input_tokens + output_tokens,
            ),
        )
        or (
            input_tokens
            + output_tokens
        )
    )

    return {

        "input_tokens":
            input_tokens,

        "output_tokens":
            output_tokens,

        "total_tokens":
            total_tokens,
    }


# =========================================================
# TOKEN-USAGE ACCUMULATION
# =========================================================

def add_usage(
    current: dict,
    new: dict,
) -> dict:

    return {

        "input_tokens":
            current.get(
                "input_tokens",
                0,
            )
            + new.get(
                "input_tokens",
                0,
            ),

        "output_tokens":
            current.get(
                "output_tokens",
                0,
            )
            + new.get(
                "output_tokens",
                0,
            ),

        "total_tokens":
            current.get(
                "total_tokens",
                0,
            )
            + new.get(
                "total_tokens",
                0,
            ),

        "model":
            settings.groq_model,
    }


# =========================================================
# TEXT CHUNKING
# =========================================================

def split_document(
    text: str,
    chunk_chars: int,
) -> list[str]:

    text = (
        text
        or ""
    ).strip()


    if not text:

        return []


    paragraphs = [
        p.strip()
        for p in text.split(
            "\n\n"
        )
        if p.strip()
    ]


    chunks = []

    current = []


    current_length = 0


    for paragraph in paragraphs:

        paragraph_length = len(
            paragraph
        )


        if (
            current
            and
            current_length
            + paragraph_length
            + 2
            > chunk_chars
        ):

            chunks.append(
                "\n\n".join(
                    current
                )
            )

            current = []

            current_length = 0


        current.append(
            paragraph
        )

        current_length += (
            paragraph_length + 2
        )


    if current:

        chunks.append(
            "\n\n".join(
                current
            )
        )


    return chunks


# =========================================================
# GRAPH NODE — PREPARE
# =========================================================

def prepare_document(
    state: AnalysisState,
):

    announcement = (
        state["announcement"]
    )

    filing_text = (
        state.get(
            "filing_text",
            "",
        )
        or ""
    )


    document = f"""
NSE ANNOUNCEMENT

Symbol:
{announcement.get("symbol", "")}

Company:
{announcement.get("company", "")}

Subject:
{announcement.get("subject", "")}

Broadcast:
{announcement.get("broadcast_raw", "")}

NSE DETAILS:
{announcement.get("details", "")}


============================================================
ATTACHED COMPANY FILING
============================================================

{filing_text}
""".strip()


    chunks = split_document(
        document,
        settings.groq_chunk_chars,
    )


    # Protect against pathological documents.
    if len(chunks) > settings.groq_max_chunks:

        max_chars = (
            settings.groq_chunk_chars
            * settings.groq_max_chunks
        )

        document = document[
            :max_chars
        ]

        chunks = split_document(
            document,
            settings.groq_chunk_chars,
        )


    return {

        "document":
            document,

        "chunks":
            chunks,
    }


# =========================================================
# GRAPH NODE — MAP
# =========================================================

def analyze_chunks(
    state: AnalysisState,
):

    llm = create_llm()

    structured = llm.with_structured_output(
        ChunkInsight,
        include_raw=True,
    )


    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                CHUNK_SYSTEM,
            ),
            (
                "human",
                """
COMPANY:
{company}

SYMBOL:
{symbol}

SUBJECT:
{subject}

FILING CHUNK:

{chunk}
""",
            ),
        ]
    )


    chain = (
        prompt
        | structured
    )


    results = []

    usage = {

        "input_tokens": 0,

        "output_tokens": 0,

        "total_tokens": 0,

        "model":
            settings.groq_model,
    }


    announcement = (
        state["announcement"]
    )


    for index, chunk in enumerate(
        state.get(
            "chunks",
            [],
        )
    ):

        result = chain.invoke(
            {
                "company":
                    announcement.get(
                        "company",
                        "",
                    ),

                "symbol":
                    announcement.get(
                        "symbol",
                        "",
                    ),

                "subject":
                    announcement.get(
                        "subject",
                        "",
                    ),

                "chunk":
                    chunk,
            }
        )


        parsed = result.get(
            "parsed"
        )

        raw = result.get(
            "raw"
        )


        if parsed is None:

            raise RuntimeError(
                "Groq structured output "
                "returned no parsed result "
                f"for chunk {index + 1}."
            )


        chunk_dict = (
            parsed.model_dump()
        )


        chunk_dict[
            "_chunk"
        ] = index + 1


        results.append(
            chunk_dict
        )


        if raw is not None:

            usage = add_usage(

                usage,

                extract_usage(
                    raw
                ),
            )


    return {

        "chunk_results":
            results,

        "usage":
            usage,
    }


# =========================================================
# GRAPH NODE — SYNTHESIS
# =========================================================

def synthesize_analysis(
    state: AnalysisState,
):

    llm = create_llm()

    structured = llm.with_structured_output(
        FinalAnalysis,
        include_raw=True,
    )


    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                FINAL_SYSTEM,
            ),
            (
                "human",
                """
Create the final institutional-style analysis.

NSE ANNOUNCEMENT:

Company:
{company}

Symbol:
{symbol}

Subject:
{subject}

NSE DETAILS:
{details}


EVIDENCE EXTRACTED FROM THE FILING:

{evidence}


Return the final structured research brief.
""",
            ),
        ]
    )


    evidence = "\n\n".join(

        f"""
--- FILING EVIDENCE BLOCK {i} ---

Material facts:
{chr(10).join(x.get("material_facts", []))}

Key numbers:
{chr(10).join(x.get("key_numbers", []))}

Management signals:
{chr(10).join(x.get("management_signals", []))}

Risks:
{chr(10).join(x.get("risks", []))}

Opportunities:
{chr(10).join(x.get("opportunities", []))}

Potential impact:
{x.get("potential_impact", "")}

Importance hint:
{x.get("importance_hint", 0)}
"""
        for i, x in enumerate(
            state.get(
                "chunk_results",
                [],
            ),
            1,
        )
    )


    chain = (
        prompt
        | structured
    )


    announcement = (
        state["announcement"]
    )


    result = chain.invoke(
        {
            "company":
                announcement.get(
                    "company",
                    "",
                ),

            "symbol":
                announcement.get(
                    "symbol",
                    "",
                ),

            "subject":
                announcement.get(
                    "subject",
                    "",
                ),

            "details":
                announcement.get(
                    "details",
                    "",
                ),

            "evidence":
                evidence,
        }
    )


    parsed = result.get(
        "parsed"
    )

    raw = result.get(
        "raw"
    )


    if parsed is None:

        raise RuntimeError(
            "Groq final structured "
            "output was empty."
        )


    usage = state.get(
        "usage",
        {},
    )


    if raw is not None:

        usage = add_usage(
            usage,
            extract_usage(
                raw
            ),
        )


    return {

        "analysis":
            parsed.model_dump(),

        "usage":
            usage,
    }


# =========================================================
# GRAPH
# =========================================================

def build_graph():

    graph = StateGraph(
        AnalysisState
    )


    graph.add_node(
        "prepare_document",
        prepare_document,
    )


    graph.add_node(
        "analyze_chunks",
        analyze_chunks,
    )


    graph.add_node(
        "synthesize_analysis",
        synthesize_analysis,
    )


    graph.add_edge(
        START,
        "prepare_document",
    )


    graph.add_edge(
        "prepare_document",
        "analyze_chunks",
    )


    graph.add_edge(
        "analyze_chunks",
        "synthesize_analysis",
    )


    graph.add_edge(
        "synthesize_analysis",
        END,
    )


    return graph.compile()


ANALYSIS_GRAPH = build_graph()


# =========================================================
# PUBLIC FUNCTION
# =========================================================

def analyze(
    announcement: dict,
    filing_text: str = "",
) -> dict:

    if not settings.groq_api_key:

        raise RuntimeError(
            "GROQ_API_KEY is not configured."
        )


    result = ANALYSIS_GRAPH.invoke(
        {
            "announcement":
                announcement,

            "filing_text":
                filing_text,
        }
    )


    return {

        "analysis":
            result["analysis"],

        "usage":
            result.get(
                "usage",
                {},
            ),
    }