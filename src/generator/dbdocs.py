"""
DBDocs Generator for GLPI Database Documentation Generator.

This module contains the DBDocsGenerator class for generating dbdocs-compatible DBML documentation.

Copyright (C) 2025 TECLIB/GLPI (glpi-project.org)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

from pathlib import Path
from typing import Dict, List, Optional

import re
import click


class DBDocsGenerator:
    """Generator for dbdocs-compatible DBML documentation."""

    def __init__(self, tables: Dict, relations: Optional[List[Dict]] = None):
        self.tables = tables
        self.relations = relations or []

    def _generate_table_definition(
            self, table_name: str, table_info: Dict) -> List[str]:
        """Generate table definition lines for DBML."""
        table_lines = [f'Table "{table_name}" {{']

        # Add columns - this is required for valid DBML
        columns = table_info.get("columns", [])
        if not columns:
            # If no columns were parsed, add a placeholder column to avoid
            # syntax error
            table_lines.append('  "id" int [pk]')
        else:
            for column in columns:
                column_line = self._format_column(column)
                table_lines.append(f"  {column_line}")

        # Add indexes if available (excluding primary key as it's already
        # marked on columns)
        non_pk_indexes = [
            idx for idx in table_info.get("indexes", [])
            if not idx.get("is_primary")
        ]
        if non_pk_indexes:
            table_lines.append("")
            table_lines.append("  Indexes {")
            for index in non_pk_indexes:
                index_line = self._format_index(index)
                table_lines.append(f"    {index_line}")
            table_lines.append("  }")

        table_lines.append("}")
        table_lines.append("")  # Empty line between tables
        return table_lines

    def _generate_relations_section(self) -> List[str]:
        """Generate relations section for DBML."""
        if not self.relations:
            return []

        dbml_content = ["// Relationships", ""]

        # Keep only relations where both endpoint tables exist.
        valid_relations = [
            r for r in self.relations
            if self._table_exists(r.get('source_table', ''))
            and self._table_exists(r.get('target_table', ''))
        ]

        # Add inferred simple relations discovered from column names.
        inferred = self._infer_relations_from_columns(valid_relations)
        if inferred:
            valid_relations.extend(inferred)

        # Sort relations by normalized source table name, then target table,
        # then by source column(s) to produce a stable, grouped ordering in
        # the generated DBML file.
        valid_relations.sort(key=self._relation_sort_key)

        for relation in valid_relations:
            relation_line = self._format_relation(relation)
            dbml_content.append(relation_line)

        dbml_content.append("")  # Empty line at the end
        return dbml_content

    def generate_dbdocs_dbml(self) -> str:
        """Generate dbdocs DBML configuration."""
        dbml_content = []

        # Generate table definitions
        for table_name, table_info in self.tables.items():
            table_lines = self._generate_table_definition(
                table_name, table_info)
            dbml_content.extend(table_lines)

        # Generate relationship definitions
        relations_section = self._generate_relations_section()
        dbml_content.extend(relations_section)

        return "\n".join(dbml_content)

    def _format_column(self, column: Dict) -> str:
        """Format a column definition for DBML."""
        parts = [f'"{column["name"]}" {column["type"]}']

        # Add constraints
        constraints = []

        if column.get("is_primary"):
            constraints.append("pk")

        if not column.get("nullable", True):
            constraints.append("not null")

        if column.get("is_auto_increment"):
            constraints.append("increment")

        if column.get("default") is not None:
            default_value = column["default"]
            if default_value == "NULL":
                constraints.append("default: NULL")
            elif isinstance(default_value, str) and default_value.upper() in [
                "CURRENT_TIMESTAMP"
            ]:
                constraints.append(f"default: `{default_value}`")
            elif isinstance(default_value, str):
                constraints.append(f"default: '{default_value}'")
            else:
                constraints.append(f"default: {default_value}")

        if column.get("comment"):
            constraints.append(f"note: '{column['comment']}'")

        if constraints:
            parts.append(f'[{", ".join(constraints)}]')

        return " ".join(parts)

    def _format_index(self, index: Dict) -> str:
        """Format an index definition for DBML."""
        quoted_columns = [f'"{col}"' for col in index["columns"]]
        if len(quoted_columns) > 1:
            columns_str = f'({", ".join(quoted_columns)})'
        else:
            columns_str = quoted_columns[0]

        if index["type"] == "UNIQUE":
            return f'{columns_str} [unique, name: "{index["name"]}"]'
        return f'{columns_str} [name: "{index["name"]}"]'

    def _table_exists(self, table_name: str) -> bool:
        """Check if a table exists in our schema, handling the "_" prefix convention.

        Args:
            table_name: Name of the table to check

        Returns:
            True if the table exists (with or without "_" prefix)
        """
        # Direct match
        if table_name in self.tables:
            return True

        # Check with "_" prefix removed
        # (for tables like "_glpi_calendars_holidays" -> "glpi_calendars_holidays")
        if table_name.startswith('_'):
            table_without_prefix = table_name[1:]  # Remove the "_" prefix
            if table_without_prefix in self.tables:
                return True

        # Check with "_" prefix added
        # (for tables like "glpi_agents" -> "_glpi_agents")
        table_with_prefix = f"_{table_name}"
        if table_with_prefix in self.tables:
            return True

        return False

    def _get_normalized_table_name(self, table_name: str) -> str:
        """Get the normalized table name that exists in our schema.

        Args:
            table_name: Original table name

        Returns:
            Normalized table name that exists in self.tables, or original if not found
        """
        # Direct match
        if table_name in self.tables:
            return table_name

        # Check with "_" prefix removed
        if table_name.startswith('_'):
            table_without_prefix = table_name[1:]
            if table_without_prefix in self.tables:
                return table_without_prefix

        # Check with "_" prefix added
        table_with_prefix = f"_{table_name}"
        if table_with_prefix in self.tables:
            return table_with_prefix

        # Return original if not found
        return table_name

    def _format_relation(self, relation: Dict) -> str:
        """Format a relationship definition for DBML.

        Args:
            relation: Dictionary containing relation information

        Returns:
            Formatted DBML relationship string
        """
        source_table = relation['source_table']
        target_table = relation['target_table']

        # Normalize table names by getting the actual table names from our
        # schema
        source_table_normalized = self._get_normalized_table_name(source_table)
        target_table_normalized = self._get_normalized_table_name(target_table)

        # Handle simple foreign key relations
        if 'source_column' in relation and 'target_column' in relation:
            source_col = relation['source_column']
            target_col = relation['target_column']
            relation_type = relation.get('relation_type', '1:n')

            return (
                f'Ref: "{source_table_normalized}"."{source_col}" > '
                f'"{target_table_normalized}"."{target_col}" // {relation_type}'
            )

        # Handle composite foreign key relations
        if 'source_columns' in relation and 'target_columns' in relation:
            source_cols = relation['source_columns']
            target_cols = relation['target_columns']
            relation_type = relation.get('relation_type', 'm:n')

            source_cols_str = ', '.join([f'"{col}"' for col in source_cols])
            target_cols_str = ', '.join([f'"{col}"' for col in target_cols])

            return (
                f'Ref: "{source_table_normalized}".({source_cols_str}) > '
                f'"{target_table_normalized}".({target_cols_str}) // {relation_type}'
            )

        # Fallback for unknown relation format
        return (
            f'// Unknown relation format: {source_table_normalized} -> '
            f'{target_table_normalized}'
        )

    def _relation_sort_key(self, rel: Dict):
        """Sorting key for relations: source, target, source columns."""
        src = self._get_normalized_table_name(rel.get('source_table', ''))
        tgt = self._get_normalized_table_name(rel.get('target_table', ''))
        if 'source_column' in rel:
            sc = rel.get('source_column') or ''
        else:
            sc = ','.join(rel.get('source_columns', []) or [])
        return (src.lower(), tgt.lower(), sc)

    def _infer_relations_from_columns(self, existing_relations: List[Dict]) -> List[Dict]:
        """Infer simple FK relations from table column names.

        Scans `self.tables` for columns matching `<base>_id` or
        `<base>_id_*` and, when a candidate referenced table exists,
        yields a simple relation if not already present in
        `existing_relations`.
        """
        existing_single = set()
        for rel in existing_relations:
            if 'source_column' in rel:
                src_norm = self._get_normalized_table_name(rel['source_table'])
                existing_single.add((src_norm, rel['source_column']))

        inferred = []
        for table_name, table_info in self.tables.items():
            src_norm = self._get_normalized_table_name(table_name)
            for col in table_info.get('columns', []):
                col_name = col.get('name')
                if not col_name:
                    continue

                m = re.match(r"^([A-Za-z0-9_]+)_id(?:_.*)?$", col_name)
                if not m:
                    continue

                base = m.group(1)
                candidates = [f"glpi_{base}", base]
                ref_table = None
                for cand in candidates:
                    if self._table_exists(cand):
                        ref_table = self._get_normalized_table_name(cand)
                        break

                if not ref_table:
                    continue

                if (src_norm, col_name) in existing_single:
                    continue

                inferred.append({
                    'source_table': table_name,
                    'target_table': ref_table,
                    'source_column': col_name,
                    'target_column': 'id',
                    'relation_type': '1:n',
                })

        return inferred

    def save_dbdocs_file(self, output_path: str):
        """Save dbdocs configuration to file."""
        dbml_content = self.generate_dbdocs_dbml()

        output_file = Path(output_path) / "dbdocs.dbml"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(dbml_content)

        click.echo(f"Generated dbdocs configuration: {output_file}")
