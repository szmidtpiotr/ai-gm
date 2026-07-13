#!/usr/bin/env python3
"""918-A2: Replace inline CREATE TABLE game_config_* in test files with _fixtures_schema helper.

Usage:
    python3 _migrate_a2.py <file1.py> [file2.py ...]
    python3 _migrate_a2.py --combat   # migrate all combat-batch files
    python3 _migrate_a2.py --spells   # migrate all spell-batch files
    python3 _migrate_a2.py --all      # migrate all batches
"""
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
IMPORT_LINE = "from _fixtures_schema import table_sql"

COMBAT_FILES = [
    "test_791_mp_combat.py",
    "test_issue232_charge_no_attack.py",
    "test_issue461_damage_bonus.py",
    "test_issue462_affix_damage.py",
    "test_issue523_hf1_scene_enemies_clear.py",
    "test_issue621_skip_turn.py",
    "test_issue734_combat_potion.py",
    "test_issue794_g17_mp_knocked.py",
    "test_issue863_offhand_equip_rules.py",
    "test_phase8_combat.py",
    "test_phase8c_combat_loot.py",
    "test_combat_gate_unified.py",
    "test_combat_v2_service.py",
    "test_combat_start_validation.py",
]

SPELL_FILES = [
    "test_issue603_s8_conditions.py",
    "test_issue604_s9_stacking.py",
    "test_issue605_s10_hemorrhage.py",
    "test_issue607_s12_hasted.py",
    "test_issue609_s14_rage_immunity.py",
    "test_issue613_s18_behavior_override.py",
    "test_issue614_s19_hidden.py",
    "test_issue645_rogue_sneak_attack.py",
    "test_issue757_narrative_item_label.py",
]


CHARACTER_FILES = [
    "test_807_g26_level_scaling.py",
    "test_issue478_xp_thresholds.py",
    "test_phase8f_cha.py",
    "test_phase9b_t21_stat_xp.py",
    "test_issue598_dual_wield.py",
    "test_issue743_hands_slot.py",
    "test_issue769_armor_auto_slot.py",
    "test_issue467_durability.py",
    "test_issue477_hidden_trait.py",
    "test_phase8e_starter_items.py",
    "test_8h_item_system.py",
    "test_issue465_resurrection_gold_sink.py",
    "test_resurrection_service.py",
    "test_issue647_resurrection_reactivates_campaign.py",
    "test_u7_skill_check_safety_net.py",
    "test_phase8c_inventory_api.py",
    "test_phase9b_t16_weapon_rules.py",
]


def find_gc_blocks(text, search_start=0, search_end=None):
    """Find all CREATE TABLE game_config_* blocks, using paren-counting to find end.

    Returns list of (abs_start, abs_end, table_name, indent_str).
    abs_start: position of \\n before CREATE TABLE
    abs_end: position after the closing );
    """
    if search_end is None:
        search_end = len(text)

    blocks = []
    pos = search_start

    while pos < search_end:
        m = re.search(
            r'(\n[ \t]*)CREATE TABLE (?:IF NOT EXISTS )?game_config_(\w+)\s*\(',
            text[pos:search_end],
        )
        if not m:
            break

        abs_start = pos + m.start()
        indent = m.group(1).lstrip("\n")  # just the spaces/tabs, without \n
        table_name = m.group(2)

        # Count parens from the opening '(' to find matching ')'
        open_pos = pos + m.end() - 1  # position of '('
        depth = 1
        i = open_pos + 1
        while i < search_end and depth > 0:
            c = text[i]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
            i += 1

        # i is now just after the closing ')'
        # skip optional whitespace then ';'
        while i < search_end and text[i] in " \t":
            i += 1
        if i < search_end and text[i] == ";":
            i += 1

        blocks.append((abs_start, i, table_name, indent))
        pos = i

    return blocks


def is_fstring(text, schema_start):
    """Check if the return statement in _schema_sql (starting at schema_start) is f-string."""
    snippet = text[schema_start : schema_start + 2000]
    return bool(re.search(r'\breturn\s+f"""', snippet))


def add_import(text):
    """Insert import after last sys.path.insert / __future__ / first normal import."""
    if "_fixtures_schema" in text:
        return text
    lines = text.split("\n")
    insert_after = None
    for i, line in enumerate(lines):
        if "sys.path.insert" in line:
            insert_after = i
    if insert_after is None:
        last_future = first_import = None
        for i, line in enumerate(lines):
            s = line.strip()
            if s.startswith("from __future__"):
                last_future = i
            elif (s.startswith("import ") or s.startswith("from ")) and first_import is None:
                first_import = i
        if last_future is not None:
            insert_after = last_future
        elif first_import is not None:
            lines.insert(first_import, IMPORT_LINE)
            return "\n".join(lines)
    if insert_after is not None:
        lines.insert(insert_after + 1, IMPORT_LINE)
    else:
        lines.insert(0, IMPORT_LINE)
    return "\n".join(lines)


def find_function_extent(text, fn_name):
    """Return (start, end) byte range of a top-level function definition."""
    m = re.search(r"\ndef " + re.escape(fn_name) + r"\b", text)
    if not m:
        return None, None
    start = m.start()
    # End: next top-level def/class or EOF
    rest = text[m.end() :]
    end_m = re.search(r"\n(?:def |class |\Z)", rest)
    end = m.end() + (end_m.start() if end_m else len(rest))
    return start, end


def migrate_file(filepath: Path) -> bool:
    text = filepath.read_text()

    if "_fixtures_schema" in text:
        print(f"  SKIP (already migrated): {filepath.name}")
        return False

    # Find _schema_sql function extent
    fn_start, fn_end = find_function_extent(text, "_schema_sql")

    # Also scan the whole file for executescript patterns outside _schema_sql
    # (e.g. _make_db, setUp, _cure_conn)
    all_blocks = find_gc_blocks(text)
    if not all_blocks:
        print(f"  SKIP (no game_config_* blocks): {filepath.name}")
        return False

    # Determine f-string status for _schema_sql
    schema_fstr = False
    if fn_start is not None:
        schema_fstr = is_fstring(text, fn_start)

    print(f"  MIGRATE: {filepath.name}  fstring_schema={schema_fstr}")
    tables_seen = []

    new_text = text
    # Process blocks from END to avoid position drift
    for abs_start, abs_end, table_name, indent in reversed(all_blocks):
        tables_seen.append(table_name)

        # Determine if this block is inside the _schema_sql f-string
        in_schema = (
            fn_start is not None
            and abs_start >= fn_start
            and abs_end <= fn_end
            and schema_fstr
        )

        if in_schema:
            # Inject into f-string: {table_sql("game_config_XXX")}
            replacement = f'\n{indent}{{table_sql("game_config_{table_name}")}}'
        else:
            # String concatenation split
            replacement = f'\n{indent}""" + table_sql("game_config_{table_name}") + """'

        new_text = new_text[:abs_start] + replacement + new_text[abs_end:]

    print(f"    tables replaced: {list(reversed(tables_seen))}")

    new_text = add_import(new_text)
    filepath.write_text(new_text)
    return True


def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: python3 _migrate_a2.py <files...> | --combat | --spells | --all")
        sys.exit(1)

    files = []
    if "--combat" in args:
        files += [HERE / f for f in COMBAT_FILES]
    if "--spells" in args:
        files += [HERE / f for f in SPELL_FILES]
    if "--characters" in args:
        files += [HERE / f for f in CHARACTER_FILES]
    if "--all" in args:
        files += [HERE / f for f in COMBAT_FILES + SPELL_FILES + CHARACTER_FILES]
    if not files:
        files = [Path(a) for a in args]

    changed = 0
    for fp in files:
        if not fp.exists():
            print(f"  NOT FOUND: {fp}")
            continue
        if migrate_file(fp):
            changed += 1

    print(f"\nMigrated {changed}/{len(files)} files.")


if __name__ == "__main__":
    main()
