#!/usr/bin/env python3
"""Apply a narrow safety patch to the pinned native PasarGuard restore library."""
from __future__ import annotations

import sys
from pathlib import Path

MARKER = "# MANUBISGUARD_RESTORE_SAFETY_V2_HELPERS"
DOLLAR_BRACE = "$" + "{"

HELPERS = r'''# MANUBISGUARD_RESTORE_SAFETY_V2_HELPERS
# Keep native archive semantics. Add a verified local PostgreSQL/TimescaleDB
# safety snapshot and rollback attempt before/after destructive database restore.
manubisguard_prepare_restore_database_safety() {
    local container_name="$1" backup_user="$2" backup_password="$3"
    local expected_database="$4" safety_parent="$5" restore_stamp="$6"
    local log_file="$7" output_var="$8"
    local safety_dir="" db_bytes="" free_bytes="" required_bytes=""
    local parent_real="" app_real="" data_real="" dbname="" owner="" has_ts="" filename="" ts_version=""
    local manifest_count=0 expected_found=false

    [ -n "$container_name" ] && [ -n "$backup_user" ] && [ -n "$backup_password" ] && [ -n "$expected_database" ] || {
        echo "Restore safety snapshot lacks a verified container, credentials, or destination database." >>"$log_file"
        return 1
    }
    parent_real=$(realpath -m -- "$safety_parent") || return 1
    app_real=$(realpath -m -- "$APP_DIR") || return 1
    data_real=$(realpath -m -- "$DATA_DIR") || return 1
    case "$parent_real" in
        "$app_real"|"$app_real/"*|"$data_real"|"$data_real/"*)
            echo "Restore safety directory must be outside APP_DIR and DATA_DIR: $parent_real" >>"$log_file"
            return 1
            ;;
    esac
    [ ! -L "$safety_parent" ] || {
        echo "Restore safety directory must not be a symlink: $safety_parent" >>"$log_file"
        return 1
    }
    if ! mkdir -p -m 0700 -- "$safety_parent"; then
        echo "Could not create restore safety directory: $safety_parent" >>"$log_file"
        return 1
    fi
    chmod 0700 "$safety_parent" || return 1

    if ! db_bytes=$(docker exec -e PGPASSWORD="$backup_password" "$container_name" \
        psql -X -v ON_ERROR_STOP=1 -U "$backup_user" -d postgres -At \
        -c "SELECT COALESCE(sum(pg_database_size(datname)),0) FROM pg_database WHERE datistemplate = false AND datallowconn = true AND datname <> 'postgres';" \
        2>>"$log_file"); then
        echo "Could not estimate database size for restore safety snapshot." >>"$log_file"
        return 1
    fi
    [[ "$db_bytes" =~ ^[0-9]+$ ]] || {
        echo "Database size estimate is invalid." >>"$log_file"
        return 1
    }
    if ! free_bytes=$(df -PB1 "$safety_parent" | awk 'NR == 2 {print $4}'); then
        echo "Could not check free space for restore safety snapshot." >>"$log_file"
        return 1
    fi
    [[ "$free_bytes" =~ ^[0-9]+$ ]] || {
        echo "Available disk space could not be determined." >>"$log_file"
        return 1
    }
    # Plain SQL dumps can grow beyond database size. Fail closed if less than
    # twice the estimated DB size plus 128 MiB is available on the snapshot FS.
    required_bytes=$((db_bytes * 2 + 134217728))
    if [ "$free_bytes" -lt "$required_bytes" ]; then
        echo "Restore safety snapshot needs at least $required_bytes bytes free; only $free_bytes are available." >>"$log_file"
        return 1
    fi

    local old_umask
    old_umask=$(umask)
    umask 077
    if ! safety_dir=$(mktemp -d "$safety_parent/restore-__DOLLAR_BRACE__{restore_stamp}.XXXXXX"); then
        umask "$old_umask"
        echo "Could not allocate a unique restore safety snapshot directory." >>"$log_file"
        return 1
    fi
    chmod 0700 "$safety_dir" || { rm -rf -- "$safety_dir"; umask "$old_umask"; return 1; }

    if ! pg_dump_all_user_databases "$container_name" "$backup_user" "$backup_password" \
        "$safety_dir" "$log_file" "$expected_database"; then
        echo "The pre-restore DB safety dump did not cover every database; refusing restore." >>"$log_file"
        rm -rf -- "$safety_dir"
        umask "$old_umask"
        return 1
    fi

    local manifest="$safety_dir/pg_dump/manifest.tsv"
    if [ ! -s "$manifest" ] || [ ! -s "$safety_dir/pg_dump/globals.sql" ] || \
        ! postgres_globals_dump_looks_complete "$safety_dir/pg_dump/globals.sql"; then
        echo "The pre-restore DB safety snapshot has incomplete globals or manifest." >>"$log_file"
        rm -rf -- "$safety_dir"
        umask "$old_umask"
        return 1
    fi

    while IFS=$'\t' read -r dbname owner has_ts filename ts_version; do
        [ -n "$dbname" ] || continue
        manifest_count=$((manifest_count + 1))
        if [ "$dbname" = "$expected_database" ]; then expected_found=true; fi
        if [ -z "$filename" ] || [ ! -s "$safety_dir/pg_dump/$filename" ] || \
            ! postgres_dump_looks_restorable "$safety_dir/pg_dump/$filename"; then
            echo "The pre-restore safety dump for database '$dbname' is missing or invalid." >>"$log_file"
            rm -rf -- "$safety_dir"
            umask "$old_umask"
            return 1
        fi
        if [ "$has_ts" = "1" ] && [ -z "$ts_version" ]; then
            echo "The pre-restore safety dump lacks the TimescaleDB version for '$dbname'." >>"$log_file"
            rm -rf -- "$safety_dir"
            umask "$old_umask"
            return 1
        fi
    done < "$manifest"

    if [ "$manifest_count" -eq 0 ] || [ "$expected_found" != true ]; then
        echo "The pre-restore safety snapshot does not contain destination database '$expected_database'." >>"$log_file"
        rm -rf -- "$safety_dir"
        umask "$old_umask"
        return 1
    fi

    if ! (cd "$safety_dir" && find pg_dump -type f -print0 | sort -z | xargs -0 -r sha256sum > safety-files.sha256); then
        echo "Could not checksum the pre-restore safety snapshot." >>"$log_file"
        rm -rf -- "$safety_dir"
        umask "$old_umask"
        return 1
    fi
    printf 'created_utc\t%s\ndatabase_type\t%s\ndestination_database\t%s\ncontainer\t%s\nproject\t%s\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$db_type" "$expected_database" "$container_name" "__DOLLAR_BRACE__{APP_NAME:-unknown}" \
        > "$safety_dir/safety-metadata.tsv"
    chmod 0600 "$safety_dir/safety-files.sha256" "$safety_dir/safety-metadata.tsv"
    : > "$safety_dir/SAFETY_SNAPSHOT_VALIDATED"
    chmod 0600 "$safety_dir/SAFETY_SNAPSHOT_VALIDATED"
    find "$safety_dir/pg_dump" -type f -exec chmod 0600 {} +
    umask "$old_umask"
    printf -v "$output_var" '%s' "$safety_dir"
    colorized_echo green "Verified pre-restore database safety snapshot saved: $safety_dir"
    return 0
}

manubisguard_verify_restore_database_safety() {
    local safety_dir="$1" dbname="" owner="" has_ts="" filename="" ts_version=""
    [ -d "$safety_dir" ] && [ ! -L "$safety_dir" ] && \
        [ -f "$safety_dir/SAFETY_SNAPSHOT_VALIDATED" ] && \
        [ -s "$safety_dir/safety-files.sha256" ] && \
        [ -s "$safety_dir/pg_dump/manifest.tsv" ] && \
        [ -s "$safety_dir/pg_dump/globals.sql" ] || return 1
    (cd "$safety_dir" && sha256sum -c safety-files.sha256 >/dev/null 2>&1) || return 1
    postgres_globals_dump_looks_complete "$safety_dir/pg_dump/globals.sql" || return 1
    while IFS=$'\t' read -r dbname owner has_ts filename ts_version; do
        [ -n "$dbname" ] || continue
        [ -s "$safety_dir/pg_dump/$filename" ] || return 1
        postgres_dump_looks_restorable "$safety_dir/pg_dump/$filename" || return 1
        if [ "$has_ts" = "1" ] && [ -z "$ts_version" ]; then return 1; fi
    done < "$safety_dir/pg_dump/manifest.tsv"
    return 0
}

manubisguard_rollback_restore_database_safety() {
    local container_name="$1" restore_user="$2" restore_password="$3"
    local admin_user="$4" admin_password="$5" safety_dir="$6" log_file="$7"
    manubisguard_verify_restore_database_safety "$safety_dir" || {
        echo "DATABASE_ROLLBACK=FAIL: saved DB snapshot failed integrity/completeness checks." >>"$log_file"
        return 1
    }
    # Restore credentials may differ from the administrative credentials needed
    # to recreate databases and apply the saved cluster globals. Keep them distinct.
    pg_restore_all_user_databases "$container_name" "$restore_user" "$restore_password" \
        "$admin_user" "$admin_password" "$safety_dir/pg_dump" "$log_file"
}
# MANUBISGUARD_RESTORE_SAFETY_V2_HELPERS_END
'''.replace("__DOLLAR_BRACE__{", DOLLAR_BRACE)

def literal(value: str) -> str:
    return value.replace("__DOLLAR_BRACE__{", DOLLAR_BRACE)

def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ValueError(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)

def patch(text: str) -> str:
    if MARKER in text:
        if (
            "manubisguard_rollback_restore_database_safety" in text
            and "DATABASE_ROLLBACK=PASS" in text
            and "MANUBISGUARD_RESTORE_SAFETY_V1_LOCK" in text
            and "sqlite_restore_started=true" in text
            and "SQLITE_ROLLBACK=PASS" in text
            and 'local admin_user="$4" admin_password="$5" safety_dir="$6" log_file="$7"' in text
            and '"$safety_admin_user" "$safety_admin_password" "$database_safety_dir" "$log_file"' in text
            and 'local restore_lock_root="${PASARGUARD_RESTORE_SAFETY_DIR:-/var/backups/pasarguard/restore-safety}"' in text
            and 'local safety_parent="${PASARGUARD_RESTORE_SAFETY_DIR:-/var/backups/pasarguard/restore-safety}"' in text
        ):
            return text
        raise ValueError("partial or inconsistent restore safety patch marker")
    restore_anchor = "# Execute interactive restore of PasarGuard databases, configurations, and data.\nrestore_command() {"
    text = replace_once(text, restore_anchor, HELPERS + "\n" + restore_anchor, "helper insertion")

    local_anchor = '    local sqlite_safety_backup=""\n    local services_stopped=false\n'
    local_new = (
        '    local sqlite_safety_backup="" sqlite_restore_started=false\n'
        '    local database_safety_dir="" database_restore_started=false\n'
        '    local safety_data_dir="" safety_app_dir="" restore_lock_fd=""\n'
        '    local services_stopped=false\n'
    )
    text = replace_once(text, local_anchor, local_new, "restore state locals")

    lock_anchor = '    done\n    if [ -n "$restore_file" ]; then'
    lock_new = r'''    done
    # MANUBISGUARD_RESTORE_SAFETY_V1_LOCK
    # Serialize mutating restore attempts per installation. --check is read-only.
    if [ "$check_only" = false ]; then
        # Keep lock/safety snapshots outside APP_DIR and DATA_DIR; BACKUP_DIR is
        # intentionally under APP_DIR in the official layout and must not be used here.
        local restore_lock_root="${PASARGUARD_RESTORE_SAFETY_DIR:-/var/backups/pasarguard/restore-safety}"
        local restore_lock_real="" app_root_real="" data_root_real=""
        app_root_real=$(realpath -m -- "$APP_DIR") || { colorized_echo red "Cannot resolve APP_DIR for restore lock."; return 1; }
        data_root_real=$(realpath -m -- "$DATA_DIR") || { colorized_echo red "Cannot resolve DATA_DIR for restore lock."; return 1; }
        restore_lock_real=$(realpath -m -- "$restore_lock_root") || { colorized_echo red "Cannot resolve restore lock directory."; return 1; }
        case "$restore_lock_real" in
            "$app_root_real"|"$app_root_real/"*|"$data_root_real"|"$data_root_real/"*)
                colorized_echo red "Restore lock directory must be outside APP_DIR and DATA_DIR."
                return 1
                ;;
        esac
        [ ! -L "$restore_lock_root" ] || { colorized_echo red "Restore lock directory must not be a symlink."; return 1; }
        mkdir -p -m 0700 -- "$restore_lock_root" || { colorized_echo red "Could not create restore lock directory."; return 1; }
        chmod 0700 "$restore_lock_root" || { colorized_echo red "Could not secure restore lock directory."; return 1; }
        local restore_lock_path="$restore_lock_root/.native-restore.lock"
        [ ! -L "$restore_lock_path" ] || { colorized_echo red "Restore lock path must not be a symlink."; return 1; }
        command -v flock >/dev/null 2>&1 || { colorized_echo red "flock is required for safe native restore."; return 1; }
        exec {restore_lock_fd}>"$restore_lock_path" || { colorized_echo red "Could not open native restore lock."; return 1; }
        chmod 0600 "$restore_lock_path" || { colorized_echo red "Could not secure native restore lock."; return 1; }
        if ! flock -n "$restore_lock_fd"; then
            colorized_echo red "Another native restore is already running for this installation. No changes were made."
            return 1
        fi
    fi
    if [ -n "$restore_file" ]; then'''
    text = replace_once(text, lock_anchor, lock_new, "restore concurrency lock")

    cleanup_prefix = 'cleanup_and_exit_restore_error() {\n        local code="$' + '{1:-1}"\n'
    cleanup_insert = r'''        local rollback_safe=true
        if [ "$database_restore_started" = true ]; then
            local safety_restore_user="$db_user" safety_restore_password="$db_password"
            local safety_admin_user="${admin_user:-$db_user}" safety_admin_password="${admin_password:-$db_password}"
            if [ -n "$current_db_user" ]; then safety_restore_user="$current_db_user"; fi
            if [ -n "$current_db_password" ]; then safety_restore_password="$current_db_password"; fi
            if [ -n "$database_safety_dir" ] && [ -n "$container_name" ] && \
                manubisguard_rollback_restore_database_safety "$container_name" "$safety_restore_user" "$safety_restore_password" "$safety_admin_user" "$safety_admin_password" "$database_safety_dir" "$log_file"; then
                echo "DATABASE_ROLLBACK=PASS: the pre-restore database snapshot was restored." >>"$log_file"
                colorized_echo yellow "The database restore failed; the pre-restore database snapshot was restored."
                database_restore_started=false
            else
                echo "DATABASE_ROLLBACK=FAIL: services must remain stopped; recover manually from the protected snapshot." >>"$log_file"
                colorized_echo red "Database rollback failed. Panel services will remain stopped; use the protected snapshot for recovery."
                rollback_safe=false
            fi
        fi
        if [ "$sqlite_restore_started" = true ]; then
            if [ -n "$sqlite_safety_backup" ] && [ -s "$sqlite_safety_backup" ] && \
                sqlite_snapshot_looks_restorable "$sqlite_safety_backup"; then
                if ! mkdir -p "$(dirname -- "$sqlite_file")" || \
                    ! rm -f "${sqlite_file}-wal" "${sqlite_file}-shm" "${sqlite_file}-journal" 2>>"$log_file" || \
                    ! cp -- "$sqlite_safety_backup" "$sqlite_file" || \
                    ! sqlite_snapshot_looks_restorable "$sqlite_file"; then
                    echo "SQLITE_ROLLBACK=FAIL: pre-restore SQLite snapshot could not be restored and verified." >>"$log_file"
                    colorized_echo red "SQLite rollback failed; application services will remain stopped."
                    rollback_safe=false
                else
                    if ! rm -f "${sqlite_file}-wal" "${sqlite_file}-shm" "${sqlite_file}-journal" 2>>"$log_file"; then
                        echo "SQLITE_ROLLBACK=FAIL: could not remove SQLite sidecar files." >>"$log_file"
                        rollback_safe=false
                    fi
                    if [ "$rollback_safe" = true ]; then
                        echo "SQLITE_ROLLBACK=PASS: the pre-restore SQLite snapshot was restored and verified." >>"$log_file"
                    fi
                fi
            else
                # No database existed before this restore; restore that absence.
                if [ -z "$sqlite_safety_backup" ] && rm -f -- "$sqlite_file" "${sqlite_file}-wal" "${sqlite_file}-shm" "${sqlite_file}-journal"; then
                    echo "SQLITE_ROLLBACK=PASS: no pre-restore SQLite database existed; partial destination removed." >>"$log_file"
                else
                    echo "SQLITE_ROLLBACK=FAIL: no valid pre-restore SQLite snapshot is available." >>"$log_file"
                    colorized_echo red "SQLite rollback failed; application services will remain stopped."
                    rollback_safe=false
                fi
            fi
        fi
        if [ -n "$safety_data_dir" ] && [ -d "$safety_data_dir" ]; then
            if rsync -a --delete "__DOLLAR_BRACE__{PASARGUARD_DATA_DIR_EXCLUDES[@]}" "$safety_data_dir/" "$DATA_DIR/" >>"$log_file" 2>&1; then
                echo "DATA_DIRECTORY_ROLLBACK=PASS" >>"$log_file"
            else
                echo "DATA_DIRECTORY_ROLLBACK=FAIL" >>"$log_file"
                colorized_echo red "Could not restore the previous data directory; panel services will remain stopped."
                rollback_safe=false
            fi
        fi
        if [ -n "$safety_app_dir" ] && [ -d "$safety_app_dir" ]; then
            if rsync -a --delete --exclude backup "$safety_app_dir/" "$APP_DIR/" >>"$log_file" 2>&1; then
                echo "APP_DIRECTORY_ROLLBACK=PASS" >>"$log_file"
            else
                echo "APP_DIRECTORY_ROLLBACK=FAIL" >>"$log_file"
                colorized_echo red "Could not restore the previous application files; panel services will remain stopped."
                rollback_safe=false
            fi
        fi
'''
    text = replace_once(text, cleanup_prefix, cleanup_prefix + literal(cleanup_insert), "error cleanup rollback logic")

    restart_anchor = '        if [ "$services_stopped" = true ] && [ "$fresh_restore" = false ] && [ "$fresh_resume" = false ]; then'
    restart_new = '        if [ "$rollback_safe" = true ] && [ "$services_stopped" = true ] && [ "$fresh_restore" = false ] && [ "$fresh_resume" = false ]; then'
    text = replace_once(text, restart_anchor, restart_new, "restart gate")

    log_anchor = '        if [ -n "$log_file" ] && [ -f "$log_file" ]; then'
    log_new = (
        '        if [ "$rollback_safe" = false ] && [ "$services_stopped" = true ]; then\n'
        '            echo "CRITICAL: rollback failed; application services were intentionally not restarted." >>"$log_file"\n'
        '        fi\n'
        + log_anchor
    )
    text = replace_once(text, log_anchor, log_new, "rollback failure log")

    safety_call = r'''    # MANUBISGUARD_RESTORE_SAFETY_V1_PREPARE
    # The application services are stopped before this point. For local PostgreSQL
    # and TimescaleDB, refuse to touch the destination until every current user DB
    # has been dumped, validated, and checksummed under a root-only safety path.
    if [ "$fresh_restore" = false ] && [ "$fresh_resume" = false ] && \
        { [ "$db_type" = "postgresql" ] || [ "$db_type" = "timescaledb" ]; } && \
        is_local_db_host "$db_host" && [ -n "$container_name" ]; then
        local safety_restore_user="$db_user" safety_restore_password="$db_password"
        if [ -n "$current_db_user" ]; then safety_restore_user="$current_db_user"; fi
        if [ -n "$current_db_password" ]; then safety_restore_password="$current_db_password"; fi
        local safety_expected_database="$db_name"
        if [ -n "$current_db_name" ]; then safety_expected_database="$current_db_name"; fi
        local safety_parent="__DOLLAR_BRACE__{PASARGUARD_RESTORE_SAFETY_DIR:-/var/backups/pasarguard/restore-safety}"
        if ! manubisguard_prepare_restore_database_safety "$container_name" "$safety_restore_user" \
            "$safety_restore_password" "$safety_expected_database" "$safety_parent" "$restore_timestamp" \
            "$log_file" database_safety_dir; then
            colorized_echo red "Could not create and verify the pre-restore DB safety snapshot. Restore aborted before database changes."
            echo "RESTORE_SAFETY_SNAPSHOT=FAIL; destination database has not been changed by this restore" >>"$log_file"
            cleanup_and_exit_restore_error 1
        fi
    fi

'''
    safety_anchor = '    # Perform restore\n    if [ "$fresh_restore" = false ]; then'
    text = replace_once(text, safety_anchor, literal(safety_call) + safety_anchor, "pre-restore snapshot gate")

    multi_anchor = (
        '                if pg_restore_all_user_databases \\\n'
        '                    "$container_name" "$restore_user" "$restore_password" "$admin_user" "$admin_password" \\\n'
    )
    multi_new = (
        '                database_restore_started=true\n'
        '                if pg_restore_all_user_databases \\\n'
        '                    "$container_name" "$restore_user" "$restore_password" "$admin_user" "$admin_password" \\\n'
    )
    text = replace_once(text, multi_anchor, multi_new, "multi-db mutation marker")

    ts_anchor = '                # Drop and recreate the target database for a clean slate\n'
    ts_new = '                # MANUBISGUARD_RESTORE_SAFETY_V1_DATABASE_MUTATION\n                database_restore_started=true\n' + ts_anchor
    text = replace_once(text, ts_anchor, ts_new, "TimescaleDB mutation marker")

    pg_anchor = (
        '                # Plain PostgreSQL restore with ON_ERROR_STOP so psql exits non-zero on SQL errors\n'
        '                colorized_echo blue "Attempting restore using app user'
    )
    pg_new = (
        '                # Plain PostgreSQL restore with ON_ERROR_STOP so psql exits non-zero on SQL errors\n'
        '                database_restore_started=true\n'
        '                colorized_echo blue "Attempting restore using app user'
    )
    text = replace_once(text, pg_anchor, pg_new, "PostgreSQL mutation marker")

    data_anchor = (
        '            if ! save_data_dir_safety_copy "$DATA_DIR.backup.$(date +%Y%m%d%H%M%S)" "$log_file"; then\n'
        '                colorized_echo red "Failed to save the current data directory before replacement."\n'
        '                cleanup_and_exit_restore_error 1\n'
        '            fi'
    )
    data_new = r'''            if ! safety_data_dir=$(mktemp -d "$DATA_DIR.backup.$restore_timestamp.XXXXXX"); then
                colorized_echo red "Failed to allocate a safety copy of the current data directory."
                cleanup_and_exit_restore_error 1
            fi
            if ! save_data_dir_safety_copy "$safety_data_dir" "$log_file"; then
                colorized_echo red "Failed to save the current data directory before replacement."
                rm -rf -- "$safety_data_dir"
                safety_data_dir=""
                cleanup_and_exit_restore_error 1
            fi'''
    text = replace_once(text, data_anchor, literal(data_new), "data directory rollback source")

    app_anchor = (
        '            if ! rsync -a --exclude backup "$APP_DIR/" "$APP_DIR.backup.$(date +%Y%m%d%H%M%S)/" 2>>"$log_file"; then\n'
        '                colorized_echo red "Failed to save the current application files before replacement."\n'
        '                cleanup_and_exit_restore_error 1\n'
        '            fi'
    )
    app_new = r'''            if ! safety_app_dir=$(mktemp -d "$APP_DIR.backup.$restore_timestamp.XXXXXX"); then
                colorized_echo red "Failed to allocate a safety copy of the current application files."
                cleanup_and_exit_restore_error 1
            fi
            if ! rsync -a --exclude backup "$APP_DIR/" "$safety_app_dir/" 2>>"$log_file"; then
                colorized_echo red "Failed to save the current application files before replacement."
                rm -rf -- "$safety_app_dir"
                safety_app_dir=""
                cleanup_and_exit_restore_error 1
            fi'''
    text = replace_once(text, app_anchor, literal(app_new), "application directory rollback source")

    sqlite_anchor = '        if cp "$sqlite_backup_source" "$sqlite_file" 2>>"$log_file"; then'
    sqlite_new = '        sqlite_restore_started=true\n' + sqlite_anchor
    text = replace_once(text, sqlite_anchor, sqlite_new, "SQLite mutation marker")

    return text

def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: manubisguard-native-restore-safety.py /path/to/pasarguard-restore.sh", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    if not path.is_file() or path.is_symlink():
        print(f"ERROR: restore library is missing or a symlink: {path}", file=sys.stderr)
        return 1
    original = path.read_text(encoding="utf-8")
    try:
        transformed = patch(original)
    except ValueError as exc:
        print(f"ERROR: native restore safety patch refused to apply: {exc}", file=sys.stderr)
        return 1
    if transformed != original:
        path.write_text(transformed, encoding="utf-8")
        print("native restore safety patch: applied")
    else:
        print("native restore safety patch: already applied")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
