"""
Conversational AI Agent.

Accepts natural language queries and converts them to SQL or structured responses.

Design:
- Primary: OpenAI GPT with function calling (if API key configured)
- Fallback: Pattern-matching NLP with pre-built query templates
- Safety: SQL is read-only (SELECT only), parameterized, schema-constrained
- Output: structured JSON with data + explanation
"""
import logging
import re
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Schema context provided to the LLM so it generates valid SQL
SCHEMA_CONTEXT = """
You are a pharmacy analytics assistant for MedAxis Platform.
Available read-only tables (PostgreSQL):

-- inventory service (medaxis_inventory)
medicines(id, name, generic_name, manufacturer, category, unit, unit_price, reorder_level)
inventory_batches(id, medicine_id, batch_number, store_id, quantity, expiry_date, is_quarantined)
stock_ledger(id, medicine_id, store_id, transaction_type, quantity_change, quantity_after, timestamp)

-- billing service (medaxis_billing)
invoices(id, invoice_number, store_id, total, status, created_at)
invoice_items(id, invoice_id, medicine_id, medicine_name, quantity, unit_price, line_total)

-- ai service (medaxis_ai)
forecast_results(id, medicine_id, medicine_name, store_id, forecast_date, predicted_demand)
anomaly_logs(id, anomaly_type, medicine_id, store_id, severity, description, detected_at)

Rules:
- Only generate SELECT statements
- Never use DROP, DELETE, UPDATE, INSERT
- Use parameterized queries where possible
- Return SQL and a plain-English explanation of what it does
"""

# Pattern-based fallback query templates
QUERY_PATTERNS = [
    {
        "patterns": [r"top.*selling", r"top.*medicines?", r"best.*selling", r"most.*sold"],
        "sql": """
            SELECT medicine_name, SUM(quantity) as total_sold
            FROM invoice_items
            JOIN invoices ON invoice_items.invoice_id = invoices.id
            WHERE invoices.status = 'CONFIRMED'
            GROUP BY medicine_name
            ORDER BY total_sold DESC
            LIMIT 10
        """,
        "explanation": "Shows the top 10 best-selling medicines by total quantity sold.",
        "db": "billing",
    },
    {
        "patterns": [r"low.?stock", r"running.?out", r"reorder"],
        "sql": """
            SELECT m.name, ib.store_id, SUM(ib.quantity) as total_stock, m.reorder_level
            FROM medicines m
            JOIN inventory_batches ib ON m.id = ib.medicine_id
            WHERE ib.expiry_date > CURRENT_DATE AND ib.is_quarantined = false
            GROUP BY m.name, ib.store_id, m.reorder_level
            HAVING SUM(ib.quantity) <= m.reorder_level
            ORDER BY total_stock ASC
        """,
        "explanation": "Lists all medicines at or below their reorder level across all stores.",
        "db": "inventory",
    },
    {
        "patterns": [r"expir", r"near.*expiry", r"expiring"],
        "sql": """
            SELECT m.name, ib.batch_number, ib.store_id, ib.quantity, ib.expiry_date
            FROM inventory_batches ib
            JOIN medicines m ON ib.medicine_id = m.id
            WHERE ib.expiry_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '90 days'
              AND ib.quantity > 0
            ORDER BY ib.expiry_date ASC
        """,
        "explanation": "Shows all batches expiring within the next 90 days.",
        "db": "inventory",
    },
    {
        "patterns": [r"sales.*today", r"today.*sales", r"revenue.*today"],
        "sql": """
            SELECT store_id, COUNT(*) as invoice_count, SUM(total) as revenue
            FROM invoices
            WHERE DATE(created_at) = CURRENT_DATE AND status = 'CONFIRMED'
            GROUP BY store_id
            ORDER BY revenue DESC
        """,
        "explanation": "Shows today's confirmed sales revenue broken down by store.",
        "db": "billing",
    },
    {
        "patterns": [r"anomal", r"unusual", r"suspicious"],
        "sql": """
            SELECT anomaly_type, medicine_id, store_id, severity, description, detected_at
            FROM anomaly_logs
            WHERE is_resolved = false
            ORDER BY detected_at DESC
            LIMIT 20
        """,
        "explanation": "Lists the 20 most recent unresolved anomalies.",
        "db": "ai",
    },
    {
        "patterns": [r"forecast", r"predict", r"demand.*next"],
        "sql": """
            SELECT medicine_name, store_id, forecast_date, predicted_demand, confidence_score
            FROM forecast_results
            WHERE forecast_date >= CURRENT_DATE
            ORDER BY forecast_date ASC, predicted_demand DESC
            LIMIT 50
        """,
        "explanation": "Shows upcoming demand forecasts ordered by date.",
        "db": "ai",
    },
]


def _pattern_match(query: str) -> Dict:
    """Try to match query against known patterns."""
    query_lower = query.lower()
    for template in QUERY_PATTERNS:
        for pattern in template["patterns"]:
            if re.search(pattern, query_lower):
                return {
                    "matched": True,
                    "sql": template["sql"].strip(),
                    "explanation": template["explanation"],
                    "db": template["db"],
                    "method": "pattern_matching",
                }
    return {"matched": False}


def _openai_query(query: str) -> Dict:
    """Use OpenAI to generate SQL from natural language."""
    try:
        import openai
        from app.config import OPENAI_API_KEY
        if not OPENAI_API_KEY:
            raise ValueError("No OpenAI API key configured")

        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SCHEMA_CONTEXT},
                {"role": "user", "content": (
                    f"Convert this question to SQL: '{query}'\n"
                    "Respond with JSON: {\"sql\": \"...\", \"explanation\": \"...\", \"db\": \"inventory|billing|ai\"}"
                )},
            ],
            temperature=0.1,
            max_tokens=500,
        )
        import json
        content = response.choices[0].message.content
        # Extract JSON from response
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            # Safety check: only allow SELECT
            sql = result.get("sql", "")
            if not sql.strip().upper().startswith("SELECT"):
                raise ValueError("Only SELECT queries are allowed")
            result["method"] = "openai_gpt"
            result["matched"] = True
            return result
    except Exception as e:
        logger.warning(f"OpenAI query failed: {e}")
    return {"matched": False}


def process_query(query: str) -> Dict[str, Any]:
    """
    Main entry point for conversational queries.
    Tries OpenAI first, falls back to pattern matching.
    """
    if not query or len(query.strip()) < 3:
        return {"error": "Query too short"}

    # Try OpenAI if available
    result = _openai_query(query)
    if result.get("matched"):
        return result

    # Fall back to pattern matching
    result = _pattern_match(query)
    if result.get("matched"):
        return result

    # No match found
    return {
        "matched": False,
        "error": "Could not understand the query",
        "suggestion": "Try asking about: top medicines, low stock, expiring batches, today's sales, anomalies, or forecasts",
        "example_queries": [
            "What are the top selling medicines?",
            "Show me low stock items",
            "Which batches are expiring soon?",
            "What are today's sales?",
            "Show recent anomalies",
        ],
    }
