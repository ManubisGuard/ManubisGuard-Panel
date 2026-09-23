from __future__ import annotations

import re


ROLE_PASSWORD_RE = re.compile(
    r"""\s+(?:(?:ENCRYPTED|UNENCRYPTED)\s+)?PASSWORD\s+(?:'([^']|'')*'|NULL)""",
    re.IGNORECASE,
)
ROLE_STMT_RE = re.compile(
    r"""^\s*(CREATE|ALTER)\s+(ROLE|USER)\s+((?:"(?:[^"]|"")*")|[A-Za-z_][A-Za-z0-9_$]*)\b""",
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

    role = _unquote_role(match.group(3))
    if destination_role and role == destination_role:
        return "", True

    sanitized, changed = ROLE_PASSWORD_RE.subn("", line)
    return sanitized, bool(changed)



def sanitize_role_password_statement(
    statement: str,
    *,
    destination_role: str | None = None,
) -> tuple[str, bool]:
    """Sanitize one complete CREATE/ALTER ROLE or USER statement."""
    match = ROLE_STMT_RE.match(statement)
    if not match:
        return statement, False
    role = _unquote_role(match.group(3))
    if destination_role and role == destination_role:
        return "", True
    transformed, count = ROLE_PASSWORD_RE.subn("", statement)
    return transformed, bool(count)


def prepare_postgresql_sql(
    source_text: str,
    *,
    destination_role: str | None = None,
) -> tuple[str, int, int]:
    """Sanitize role/password statements, including multiline statements."""
    output: list[str] = []
    passwords_removed = 0
    destination_role_statements = 0
    pending: list[str] = []
    pending_role = False

    def emit(statement: str) -> None:
        nonlocal passwords_removed, destination_role_statements
        transformed, changed = sanitize_role_password_statement(
            statement,
            destination_role=destination_role,
        )
        if transformed == "" and changed:
            destination_role_statements += 1
            return
        if changed:
            passwords_removed += 1
        output.append(transformed)

    for raw_line in source_text.splitlines():
        if not pending and ROLE_STMT_RE.match(raw_line):
            pending_role = True
        if pending_role:
            pending.append(raw_line)
            if ";" in raw_line:
                emit("\n".join(pending))
                pending.clear()
                pending_role = False
            continue
        transformed, changed = sanitize_role_password_line(
            raw_line,
            destination_role=destination_role,
        )
        if changed:
            passwords_removed += 1
        if transformed == "" and changed and ROLE_STMT_RE.match(raw_line):
            destination_role_statements += 1
            continue
        output.append(transformed)

    if pending:
        emit("\n".join(pending))

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
    """Stream-sanitize role statements, including multiline CREATE/ALTER USER/ROLE."""
    passwords_removed = 0
    destination_role_statements = 0
    pending: list[str] = []
    pending_role = False

    def emit(statement: str) -> None:
        nonlocal passwords_removed, destination_role_statements
        transformed, changed = sanitize_role_password_statement(
            statement,
            destination_role=destination_role,
        )
        if transformed == "" and changed:
            destination_role_statements += 1
            return
        if changed:
            passwords_removed += 1
        destination.write(transformed + "\n")

    for raw_line in source:
        line = raw_line.rstrip("\r\n")
        if not pending and ROLE_STMT_RE.match(line):
            pending_role = True
        if pending_role:
            pending.append(line)
            if ";" in line:
                emit("\n".join(pending))
                pending.clear()
                pending_role = False
            continue
        transformed, changed = sanitize_role_password_line(
            line,
            destination_role=destination_role,
        )
        if transformed == "" and changed and ROLE_STMT_RE.match(line):
            destination_role_statements += 1
            continue
        if changed:
            passwords_removed += 1
        destination.write(transformed + ("\n" if raw_line.endswith("\n") else ""))

    if pending:
        emit("\n".join(pending))

    return passwords_removed, destination_role_statements
