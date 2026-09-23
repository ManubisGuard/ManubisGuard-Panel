from app.migration.inspector import ForeignKeyInfo
from app.migration.validator import _orphan_sql


def test_orphan_query_is_quoted_for_identifiers():
    fk = ForeignKeyInfo(
        table="users",
        constrained_columns=("node_id",),
        referred_table="nodes",
        referred_columns=("id",),
    )
    sql = _orphan_sql(fk)
    assert 'public."users"' in sql
    assert 'public."nodes"' in sql
    assert 's."node_id" = t."id"' in sql
    assert 's."node_id" IS NOT NULL' in sql
