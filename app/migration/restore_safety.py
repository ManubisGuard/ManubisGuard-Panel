from __future__ import annotations

import re


ROLE_PASSWORD_RE = re.compile(
    r"""\s+(?:(?:ENCRYPTED|UNENCRYPTED)\s+)?PASSWORD\s+(?:'([^']|'')*'|NULL)""",
    re.IGNORECASE,
)
ROLE_STMT_RE = re.compile(
    r"""^\s*(CREATE|ALTER)\s+ROLE\s+((?:"(?:[^"]|"")*")|[A-Za-z_][A-Za-z0-9_$]*)\b""",
    re.IGNORECASE,
)


def _unquote_role(identifier: str) -> str:
    identifier = identifier.strip()
    if len(identifier) >= 2 and identifier[0] == '"' and identifier[-1] == '"':
        return identifier[1:-1].replace('""', '"')
    return identifier


def sanitize_role_password_line(
    line: str,
    *,
    destination_role: str | None = None,
) -> tuple[str, bool]:
    """Remove archived PostgreSQL role passwords and protect the destination role.

    This mirrors the PasarGuard restore safety rule: credentials from the backup
    belong to the source installation and must never replace the destination
    database role password. The destination role's CREATE/ALTER ROLE statements
    are dropped completely so its existing privileges and connection settings
    remain authoritative.
    """
    match = ROLE_STMT_RE.match(line)
    if not match:
        return line, False

    role = _unquote_role(match.group(2))
    if destination_role and role == destination_role:
        return "", True

    sanitized, changed = ROLE_PASSWORD_RE.subn("", line)
    return sanitized, bool(changed)


def prepare_postgresql_sql(
    source_text: str,
    *,
    destination_role: str | None = None,
) -> tuple[str, int, int]:
    """Sanitize role/password statements in a PostgreSQL plain-SQL dump.

    Returns the transformed SQL, number of password clauses removed, and number
    of destination-role statements suppressed.
    """
    output: list[str] = []
    passwords_removed = 0
    destination_role_statements = 0

    for line in source_text.splitlines():
        transformed, changed = sanitize_role_password_line(
            line,
            destination_role=destination_role,
        )
        if transformed == "" and changed and ROLE_STMT_RE.match(line):
            role = _unquote_role(ROLE_STMT_RE.match(line).group(2))
            if destination_role and role == destination_role:
                destination_role_statements += 1
                continue

        if transformed != line:
            passwords_removed += 1
        output.append(transformed)

    text = "\n".join(output)
    if source_text.endswith(("\n", "\r")):
        text += "\n"
    return text, passwords_removed, destination_role_statements


def prepare_postgresql_sql_stream(
    source,
    destination,
    *,
    destination_role: str | None = None,
) -> tuple[int, int]:
    """Stream-sanitize a PostgreSQL SQL dump without loading it into memory."""
    passwords_removed = 0
    destination_role_statements = 0

    for raw_line in source:
        line = raw_line.rstrip("\r\n")
        transformed, changed = sanitize_role_password_line(
            line,
            destination_role=destination_role,
        )
        role_match = ROLE_STMT_RE.match(line)
        if transformed == "" and changed and role_match:
            role = _unquote_role(role_match.group(2))
            if destination_role and role == destination_role:
                destination_role_statements += 1
                continue

        if transformed != line:
            passwords_removed += 1
        destination.write(
            transformed + ("\n" if raw_line.endswith("\n") else "")
        )

    return passwords_removed, destination_role_statements
