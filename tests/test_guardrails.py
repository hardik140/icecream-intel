import pytest

from app.guardrails.input_guard import scrub_pii
from app.guardrails.output_guard import ungrounded_numbers
from app.guardrails.sql_guard import check_sql


@pytest.mark.parametrize("sql", [
    "SELECT * FROM sales",
    "WITH t AS (SELECT flavour FROM sales) SELECT * FROM t",
    "SELECT 1 UNION ALL SELECT 2",
])
def test_sql_guard_allows_reads(sql):
    assert check_sql(sql, 50).endswith("LIMIT 50")


@pytest.mark.parametrize("sql", [
    "DROP TABLE sales",
    "DELETE FROM sales",
    "INSERT INTO sales VALUES (1)",
    "UPDATE sales SET units_sold = 0",
    "CREATE TABLE x AS SELECT 1",
    "SELECT 1; DROP TABLE sales",
    "ATTACH 'other.db'",
    "COPY sales TO 'out.csv'",
    "PRAGMA database_list",
    "SET enable_external_access = true",
    "not sql at all (((",
])
def test_sql_guard_blocks_everything_else(sql):
    with pytest.raises(ValueError):
        check_sql(sql)


def test_scrub_pii():
    out = scrub_pii("Mail a.b@x.com or call +91 98765 43210, card 4111 1111 1111 1111. Sales in 2025?")
    assert out == "Mail [EMAIL] or call [PHONE], card [CARD]. Sales in 2025?"


def test_ungrounded_numbers():
    sources = 'SQL RESULT: [{"revenue": 12685680.0, "pct": -23.0912}]'
    assert ungrounded_numbers("Revenue was 12,685,680 and fell 23.09% in the top 3", sources) == []
    assert ungrounded_numbers("Revenue was 13,000,000", sources) == [13000000.0]
