from __future__ import annotations

from email.message import EmailMessage
from html import escape

import smtplib

from .config import settings


# ============================================================
# SMTP VALIDATION
# ============================================================

def _validate_smtp() -> None:

    missing = []

    if not settings.smtp_host:
        missing.append("SMTP_HOST")

    if not settings.smtp_user:
        missing.append("SMTP_USER")

    if not settings.smtp_password:
        missing.append("SMTP_PASSWORD")

    if not settings.smtp_from:
        missing.append("SMTP_FROM")

    if missing:

        raise RuntimeError(
            "SMTP is not configured. Missing: "
            + ", ".join(missing)
        )


# ============================================================
# SMTP CONNECTION
# ============================================================

def _send_message(message: EmailMessage) -> None:

    _validate_smtp()

    with smtplib.SMTP(
        settings.smtp_host,
        settings.smtp_port,
        timeout=30,
    ) as smtp:

        if settings.smtp_starttls:

            smtp.starttls()

        smtp.login(
            settings.smtp_user,
            settings.smtp_password,
        )

        smtp.send_message(message)


# ============================================================
# SMALL HELPERS
# ============================================================

def _safe_list(
    values,
    fallback: str,
) -> str:

    if not values:

        return f"<li>{escape(fallback)}</li>"

    return "".join(
        f"<li>{escape(str(value))}</li>"
        for value in values
    )


def _impact_class(
    impact: str,
) -> str:

    return {

        "positive": "impact-positive",

        "negative": "impact-negative",

        "mixed": "impact-mixed",

        "neutral": "impact-neutral",

        "unclear": "impact-neutral",

    }.get(
        str(impact).lower(),
        "impact-neutral",
    )


# ============================================================
# SINGLE ANNOUNCEMENT HTML EMAIL
# ============================================================

def build_single_html_email(
    announcement: dict,
    analysis: dict,
) -> str:

    symbol = announcement.get(
        "symbol",
        "",
    )

    company = announcement.get(
        "company",
        "",
    )

    headline = (
        analysis.get(
            "headline"
        )
        or announcement.get(
            "subject",
            "NSE Announcement",
        )
    )

    importance = int(
        analysis.get(
            "importance",
            0,
        )
    )

    importance = max(
        0,
        min(
            importance,
            100,
        ),
    )

    impact = str(
        analysis.get(
            "impact",
            "unclear",
        )
    )

    event_type = str(
        analysis.get(
            "event_type",
            "other",
        )
    )

    filing_url = announcement.get(
        "attachment_url"
    )

    filing_button = ""

    if filing_url:

        filing_button = f"""
        <a
            href="{escape(filing_url)}"
            target="_blank"
            style="
                display:inline-block;
                margin-top:24px;
                color:#c7a35e;
                text-decoration:none;
                font-size:11px;
                letter-spacing:1px;
                font-weight:bold;
            "
        >
            VIEW ORIGINAL NSE FILING →
        </a>
        """

    return f"""
<!DOCTYPE html>

<html>

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
>

<title>
South Decan Capital
</title>

</head>

<body
    style="
        margin:0;
        padding:0;
        background:#070809;
        color:#e9e4da;
        font-family:Arial,Helvetica,sans-serif;
    "
>

<table
    width="100%"
    cellpadding="0"
    cellspacing="0"
    border="0"
    style="background:#070809;"
>

<tr>

<td
    align="center"
    style="padding:45px 18px;"
>

<table
    width="760"
    cellpadding="0"
    cellspacing="0"
    border="0"
    style="
        width:100%;
        max-width:760px;
        background:#0f1012;
        border:1px solid #292a2d;
    "
>


<!-- BRAND -->

<tr>

<td
    style="
        padding:35px 35px 12px 35px;
    "
>

<div
    style="
        color:#c7a35e;
        font-size:11px;
        letter-spacing:5px;
        font-weight:bold;
    "
>
    SOUTH DECAN CAPITAL
</div>


<div
    style="
        color:#f0ece3;
        font-family:Georgia,serif;
        font-size:32px;
        font-weight:normal;
        margin-top:12px;
    "
>
    NSE Corporate Intelligence
</div>


<div
    style="
        color:#77797e;
        font-size:12px;
        margin-top:6px;
    "
>
    AI-Assisted Equity Research Brief
</div>

</td>

</tr>


<!-- META -->

<tr>

<td
    style="
        padding:15px 35px;
        border-top:1px solid #292a2d;
        border-bottom:1px solid #292a2d;
        color:#77797e;
        font-size:10px;
    "
>

{escape(symbol)}
&nbsp; • &nbsp;
{escape(company)}
&nbsp; • &nbsp;
{escape(event_type)}

</td>

</tr>


<!-- CONTENT -->

<tr>

<td
    style="padding:35px;"
>


<div>

<span
    style="
        display:inline-block;
        background:#c7a35e;
        color:#111;
        padding:6px 10px;
        border-radius:4px;
        font-size:10px;
        font-weight:bold;
    "
>
{escape(symbol)}
</span>


<span
    style="
        margin-left:8px;
        color:#8b8c91;
        font-size:9px;
        text-transform:uppercase;
        letter-spacing:1px;
    "
>
{escape(event_type)}
</span>

</div>


<h1
    style="
        margin:20px 0 18px 0;
        color:#f1ede4;
        font-family:Georgia,serif;
        font-size:27px;
        line-height:1.35;
        font-weight:normal;
    "
>
{escape(headline)}
</h1>


<!-- IMPACT -->

<div
    style="
        display:inline-block;
        padding:6px 10px;
        border-radius:5px;
        font-size:9px;
        letter-spacing:1px;
        font-weight:bold;
        background:
        {
            "#10251b"
            if impact.lower() == "positive"
            else
            "#291515"
            if impact.lower() == "negative"
            else
            "#292314"
            if impact.lower() == "mixed"
            else
            "#202125"
        };
        color:
        {
            "#78c995"
            if impact.lower() == "positive"
            else
            "#e08383"
            if impact.lower() == "negative"
            else
            "#d5b86c"
            if impact.lower() == "mixed"
            else
            "#9d9da2"
        };
    "
>
{escape(impact.upper())}
</div>


<!-- SCORE -->

<div
    style="margin-top:25px;"
>

<div
    style="
        font-size:10px;
        color:#777;
        display:flex;
        justify-content:space-between;
    "
>

<span>
Materiality
</span>

<strong
    style="
        color:#c7a35e;
    "
>
{importance}/100
</strong>

</div>


<div
    style="
        height:4px;
        margin-top:7px;
        background:#292a2d;
        border-radius:4px;
    "
>

<div
    style="
        width:{importance}%;
        height:4px;
        background:#c7a35e;
        border-radius:4px;
    "
>
</div>

</div>

</div>


<!-- SUMMARY -->

<div
    style="
        margin-top:25px;
        color:#d3cec5;
        font-size:14px;
        line-height:1.8;
    "
>

{escape(
    analysis.get(
        "executive_summary",
        analysis.get(
            "summary",
            ""
        ),
    )
)}

</div>


<!-- WHY -->

<div
    style="
        margin-top:26px;
        border-left:2px solid #c7a35e;
        background:#151515;
        padding:15px;
    "
>

<div
    style="
        color:#c7a35e;
        font-size:9px;
        font-weight:bold;
        letter-spacing:1.5px;
    "
>
WHY IT MATTERS
</div>


<div
    style="
        color:#999;
        font-size:12px;
        line-height:1.7;
        margin-top:6px;
    "
>

{escape(
    analysis.get(
        "why_it_matters",
        ""
    )
)}

</div>

</div>


<!-- FINANCIAL / OPERATIONAL -->

<table
    width="100%"
    cellpadding="0"
    cellspacing="0"
    style="margin-top:25px;"
>

<tr>

<td
    width="50%"
    valign="top"
    style="padding-right:12px;"
>

<div
    style="
        color:#c7a35e;
        font-size:9px;
        letter-spacing:1.5px;
        font-weight:bold;
        margin-bottom:7px;
    "
>
FINANCIAL IMPACT
</div>

<div
    style="
        color:#999;
        font-size:12px;
        line-height:1.7;
    "
>

{escape(
    analysis.get(
        "financial_impact",
        "Not disclosed.",
    )
)}

</div>

</td>


<td
    width="50%"
    valign="top"
    style="padding-left:12px;"
>

<div
    style="
        color:#c7a35e;
        font-size:9px;
        letter-spacing:1.5px;
        font-weight:bold;
        margin-bottom:7px;
    "
>
OPERATIONAL IMPACT
</div>

<div
    style="
        color:#999;
        font-size:12px;
        line-height:1.7;
    "
>

{escape(
    analysis.get(
        "operational_impact",
        "Not disclosed.",
    )
)}

</div>

</td>

</tr>

</table>


<!-- FACTS -->

<div style="margin-top:27px;">

<div
    style="
        color:#c7a35e;
        font-size:9px;
        letter-spacing:1.5px;
        font-weight:bold;
    "
>
KEY FACTS
</div>

<ul
    style="
        margin-top:7px;
        padding-left:18px;
    "
>

{_safe_list(
    analysis.get(
        "key_facts",
        []
    ),
    "See original filing.",
)}

</ul>

</div>


<!-- NUMBERS -->

<div style="margin-top:24px;">

<div
    style="
        color:#c7a35e;
        font-size:9px;
        letter-spacing:1.5px;
        font-weight:bold;
    "
>
KEY NUMBERS
</div>

<ul
    style="
        margin-top:7px;
        padding-left:18px;
    "
>

{_safe_list(
    analysis.get(
        "key_numbers",
        []
    ),
    "None disclosed.",
)}

</ul>

</div>


<!-- OPPORTUNITIES / RISKS -->

<table
    width="100%"
    cellpadding="0"
    cellspacing="0"
    style="margin-top:25px;"
>

<tr>

<td
    width="50%"
    valign="top"
    style="padding-right:12px;"
>

<div
    style="
        color:#c7a35e;
        font-size:9px;
        letter-spacing:1.5px;
        font-weight:bold;
    "
>
OPPORTUNITIES
</div>

<ul
    style="
        padding-left:18px;
    "
>

{_safe_list(
    analysis.get(
        "opportunities",
        []
    ),
    "No specific opportunity disclosed.",
)}

</ul>

</td>


<td
    width="50%"
    valign="top"
    style="padding-left:12px;"
>

<div
    style="
        color:#c7a35e;
        font-size:9px;
        letter-spacing:1.5px;
        font-weight:bold;
    "
>
RISKS
</div>

<ul
    style="
        padding-left:18px;
    "
>

{_safe_list(
    analysis.get(
        "risks",
        []
    ),
    "No specific risk disclosed.",
)}

</ul>

</td>

</tr>

</table>


<!-- WATCH -->

<div
    style="
        margin-top:25px;
        padding:16px;
        background:#151515;
        border-left:2px solid #c7a35e;
    "
>

<div
    style="
        color:#c7a35e;
        font-size:9px;
        font-weight:bold;
        letter-spacing:1.5px;
    "
>
WHAT TO WATCH
</div>


<ul
    style="
        padding-left:18px;
        margin-bottom:0;
    "
>

{_safe_list(
    analysis.get(
        "watch_items",
        []
    ),
    "No specific follow-up disclosed.",
)}

</ul>

</div>


{filing_button}


</td>

</tr>


<!-- FOOTER -->

<tr>

<td
    style="
        padding:22px 35px 30px 35px;
        border-top:1px solid #292a2d;
        color:#555;
        font-size:9px;
        line-height:1.6;
    "
>

South Decan Capital<br>

Automated AI-assisted analysis of
NSE/company filings.<br>

Verify material facts against the
original filing. Not investment advice.

</td>

</tr>

</table>

</td>

</tr>

</table>

</body>

</html>
"""


# ============================================================
# SINGLE EMAIL
# ============================================================

def send_email(
    to: str,
    announcement: dict,
    analysis: dict,
):

    subject = (
        "South Decan Capital | "
        f"{announcement.get('symbol', '')} | "
        f"{analysis.get('headline') or announcement.get('subject', 'NSE Filing')}"
    )


    plain_text = f"""

SOUTH DECAN CAPITAL

NSE CORPORATE INTELLIGENCE

Company:
{announcement.get("company", "")}

Symbol:
{announcement.get("symbol", "")}

Event:
{analysis.get("event_type", "other")}

Importance:
{analysis.get("importance", 0)}/100

Impact:
{analysis.get("impact", "unclear")}

SUMMARY
{analysis.get("executive_summary", analysis.get("summary", ""))}

WHY IT MATTERS
{analysis.get("why_it_matters", "")}

FINANCIAL IMPACT
{analysis.get("financial_impact", "Not disclosed.")}

OPERATIONAL IMPACT
{analysis.get("operational_impact", "Not disclosed.")}

KEY FACTS
{chr(10).join("- " + str(x) for x in analysis.get("key_facts", []))}

KEY NUMBERS
{chr(10).join("- " + str(x) for x in analysis.get("key_numbers", []))}

OPPORTUNITIES
{chr(10).join("- " + str(x) for x in analysis.get("opportunities", []))}

RISKS
{chr(10).join("- " + str(x) for x in analysis.get("risks", []))}

WHAT TO WATCH
{chr(10).join("- " + str(x) for x in analysis.get("watch_items", []))}

ORIGINAL FILING
{announcement.get("attachment_url", "Not available")}

South Decan Capital
Automated AI-assisted analysis.
Not investment advice.
"""


    message = EmailMessage()

    message["From"] = (
        settings.smtp_from
    )

    message["To"] = to

    message["Subject"] = subject

    message.set_content(
        plain_text
    )

    message.add_alternative(
        build_single_html_email(
            announcement,
            analysis,
        ),
        subtype="html",
    )

    _send_message(message)


# ============================================================
# WATCHLIST DIGEST
# ============================================================

def send_watchlist_digest(
    to: str,
    items: list[dict],
):

    if not items:

        raise ValueError(
            "No analyzed announcements to send."
        )


    items = sorted(

        items,

        key=lambda item:
            int(
                item["analysis"].get(
                    "importance",
                    0,
                )
            ),

        reverse=True,
    )


    # Reuse the single-report HTML layout by composing cards.
    cards = []


    for item in items:

        announcement = (
            item["announcement"]
        )

        analysis = (
            item["analysis"]
        )


        symbol = announcement.get(
            "symbol",
            "",
        )

        headline = (
            analysis.get(
                "headline"
            )
            or announcement.get(
                "subject",
                "NSE Announcement",
            )
        )


        importance = max(
            0,
            min(
                100,
                int(
                    analysis.get(
                        "importance",
                        0,
                    )
                ),
            ),
        )


        impact = str(
            analysis.get(
                "impact",
                "unclear",
            )
        )


        impact_bg = {

            "positive": "#10251b",

            "negative": "#291515",

            "mixed": "#292314",

        }.get(
            impact.lower(),
            "#202125",
        )


        impact_color = {

            "positive": "#78c995",

            "negative": "#e08383",

            "mixed": "#d5b86c",

        }.get(
            impact.lower(),
            "#9d9da2",
        )


        filing_url = announcement.get(
            "attachment_url"
        )


        filing = ""

        if filing_url:

            filing = f"""
                <a
                    href="{escape(filing_url)}"
                    target="_blank"
                    style="
                        color:#c7a35e;
                        text-decoration:none;
                        font-size:10px;
                        font-weight:bold;
                        letter-spacing:1px;
                    "
                >
                    ORIGINAL FILING →
                </a>
            """


        cards.append(

            f"""
            <div
                style="
                    margin-top:20px;
                    padding:25px;
                    background:#111214;
                    border:1px solid #292a2d;
                "
            >

                <div>

                    <span
                        style="
                            display:inline-block;
                            background:#c7a35e;
                            color:#111;
                            padding:6px 10px;
                            border-radius:4px;
                            font-size:10px;
                            font-weight:bold;
                        "
                    >
                        {escape(symbol)}
                    </span>

                    <span
                        style="
                            margin-left:8px;
                            padding:6px 9px;
                            background:{impact_bg};
                            color:{impact_color};
                            border-radius:4px;
                            font-size:9px;
                        "
                    >
                        {escape(impact.upper())}
                    </span>

                </div>


                <h2
                    style="
                        font-family:Georgia,serif;
                        font-weight:normal;
                        font-size:22px;
                        color:#eee9df;
                        line-height:1.35;
                    "
                >
                    {escape(headline)}
                </h2>


                <div
                    style="
                        display:flex;
                        justify-content:space-between;
                        font-size:10px;
                        color:#777;
                    "
                >

                    <span>
                        Materiality
                    </span>

                    <strong
                        style="color:#c7a35e;"
                    >
                        {importance}/100
                    </strong>

                </div>


                <div
                    style="
                        height:4px;
                        background:#292a2d;
                        margin-top:7px;
                    "
                >

                    <div
                        style="
                            width:{importance}%;
                            height:4px;
                            background:#c7a35e;
                        "
                    ></div>

                </div>


                <p
                    style="
                        color:#bbb7af;
                        font-size:13px;
                        line-height:1.7;
                    "
                >
                    {escape(
                        analysis.get(
                            "executive_summary",
                            analysis.get(
                                "summary",
                                "",
                            ),
                        )
                    )}
                </p>


                <div
                    style="
                        margin-top:15px;
                        border-left:2px solid #c7a35e;
                        padding-left:12px;
                    "
                >

                    <div
                        style="
                            color:#c7a35e;
                            font-size:9px;
                            letter-spacing:1px;
                            font-weight:bold;
                        "
                    >
                        WHY IT MATTERS
                    </div>

                    <p
                        style="
                            color:#999;
                            font-size:11px;
                            line-height:1.7;
                        "
                    >
                        {escape(
                            analysis.get(
                                "why_it_matters",
                                "",
                            )
                        )}
                    </p>

                </div>


                <div
                    style="margin-top:16px;"
                >

                    {filing}

                </div>

            </div>
            """
        )


    html = f"""
<!DOCTYPE html>

<html>

<head>

<meta charset="UTF-8">

</head>

<body
style="
    margin:0;
    background:#070809;
    color:#eee;
    font-family:Arial,Helvetica,sans-serif;
"
>

<div
style="
    max-width:760px;
    margin:auto;
    padding:45px 18px;
"
>

<div
style="
    color:#c7a35e;
    font-size:11px;
    letter-spacing:5px;
    font-weight:bold;
"
>
SOUTH DECAN CAPITAL
</div>


<h1
style="
    font-family:Georgia,serif;
    font-weight:normal;
    font-size:34px;
    color:#f1ece3;
    margin-bottom:5px;
"
>
NSE Corporate Intelligence
</h1>


<div
style="
    color:#777;
    font-size:12px;
"
>
AI-Assisted Equity Research Brief
</div>


<div
style="
    margin-top:27px;
    padding:13px 0;
    border-top:1px solid #292a2d;
    border-bottom:1px solid #292a2d;
    color:#777;
    font-size:10px;
"
>
{len(items)} filing(s) analysed
</div>


{"".join(cards)}


<div
style="
    margin-top:30px;
    border-top:1px solid #292a2d;
    padding-top:18px;
    color:#555;
    font-size:9px;
    line-height:1.6;
"
>
South Decan Capital — automated AI-assisted
analysis of NSE/company filings.
Verify important facts against the original filing.
Not investment advice.
</div>

</div>

</body>

</html>
"""


    plain_parts = [

        "SOUTH DECAN CAPITAL",

        "NSE CORPORATE INTELLIGENCE",

        "",

        f"{len(items)} filing(s) analysed.",

        "",
    ]


    for i, item in enumerate(
        items,
        1,
    ):

        a = item[
            "announcement"
        ]

        x = item[
            "analysis"
        ]


        plain_parts.extend(

            [

                (
                    f"{i}. "
                    f"{a.get('symbol', '')} — "
                    f"{x.get('headline', '')}"
                ),

                (
                    f"Importance: "
                    f"{x.get('importance', 0)}/100"
                ),

                (
                    f"Impact: "
                    f"{x.get('impact', 'unclear')}"
                ),

                "",

                x.get(
                    "executive_summary",
                    x.get(
                        "summary",
                        "",
                    ),
                ),

                "",

            ]
        )


    plain_parts.append(
        "Verify material facts against the original filing. "
        "Not investment advice."
    )


    message = EmailMessage()

    message["From"] = (
        settings.smtp_from
    )

    message["To"] = to

    message["Subject"] = (
        "South Decan Capital | "
        "NSE Intelligence | "
        f"{len(items)} filings"
    )

    message.set_content(
        "\n".join(
            plain_parts
        )
    )

    message.add_alternative(
        html,
        subtype="html",
    )

    _send_message(message)


# ============================================================
# SMTP TEST
# ============================================================

def send_test_email(
    to: str,
):

    message = EmailMessage()

    message["From"] = (
        settings.smtp_from
    )

    message["To"] = to

    message["Subject"] = (
        "South Decan Capital | "
        "SMTP Test"
    )

    message.set_content(
        """
South Decan Capital

SMTP TEST SUCCESSFUL

Your NSE corporate-intelligence
email configuration is working.
"""
    )

    message.add_alternative(
        """
        <!DOCTYPE html>

        <html>

        <body
        style="
            background:#070809;
            color:#eee;
            font-family:Arial;
            padding:40px;
        "
        >

        <div
        style="
            max-width:600px;
            margin:auto;
            background:#101113;
            padding:35px;
            border:1px solid #292a2d;
        "
        >

            <div
            style="
                color:#c7a35e;
                font-size:11px;
                letter-spacing:5px;
                font-weight:bold;
            "
            >
            SOUTH DECAN CAPITAL
            </div>

            <h1
            style="
                color:#eee;
                font-family:Georgia,serif;
                font-weight:normal;
            "
            >
            SMTP Test Successful
            </h1>

            <p
            style="
                color:#999;
                font-size:13px;
                line-height:1.7;
            "
            >
            Your NSE corporate-intelligence
            email pipeline is configured correctly.
            </p>

        </div>

        </body>

        </html>
        """,
        subtype="html",
    )

    _send_message(message)