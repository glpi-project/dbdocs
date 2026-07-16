"""
SQL Parser for GLPI Database Documentation Generator.

This module contains the GLPIDatabaseParser class for parsing GLPI SQL installation files.

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

import re
from typing import Dict, List, Optional

import click
import sqlparse


class GLPIDatabaseParser:
    """Parser for GLPI SQL installation files."""

    def __init__(self, sql_file_path: str):
        self.sql_file_path = sql_file_path
        self.tables = {}

    def parse_sql_file(self) -> Dict:
        """Parse the SQL file and extract table definitions."""
        try:
            with open(self.sql_file_path, "r", encoding="utf-8") as file:
                sql_content = file.read()
        except FileNotFoundError as exc:
            raise click.ClickException(
                f"SQL file not found: {self.sql_file_path}") from exc
        except Exception as e:
            raise click.ClickException(
                f"Error reading SQL file: {str(e)}") from e

        # Parse SQL using sqlparse
        parsed = sqlparse.parse(sql_content)

        for statement in parsed:
            if statement.get_type() == "CREATE":
                self._parse_create_statement(statement)

        return self.tables

    def get_tables(self) -> Dict:
        """Get the parsed tables dictionary."""
        return self.tables

    def _parse_create_statement(self, statement):
        """Parse CREATE TABLE statements."""
        # Convert statement to string for easier parsing
        sql_str = str(statement)

        # Extract table name using regex
        table_match = re.search(
            r'CREATE\s+TABLE\s+[`"]?(\w+)[`"]?\s*\(', sql_str, re.IGNORECASE
        )
        if not table_match:
            return

        table_name = table_match.group(1)

        # Extract the column definitions section
        column_section_match = re.search(
            r'CREATE\s+TABLE\s+[`"]?\w+[`"]?\s*\((.*?)\)\s*ENGINE',
            sql_str,
            re.IGNORECASE | re.DOTALL,
        )
        if not column_section_match:
            return

        column_section = column_section_match.group(1)

        # Extract table comment separately
        table_comment_match = re.search(
            r"ENGINE.*?COMMENT\s*=\s*\'([^\']*)\'", sql_str, re.IGNORECASE | re.DOTALL
        )
        table_comment = table_comment_match.group(
            1) if table_comment_match else ""

        # Parse columns
        columns = self._parse_columns_from_string(column_section)

        # Extract indexes
        indexes = self._extract_indexes_from_string(column_section)

        # Mark primary key columns
        for column in columns:
            if column["name"] in [
                idx["columns"][0] for idx in indexes if idx.get("is_primary")
            ]:
                column["is_primary"] = True

        self.tables[table_name] = {
            "name": table_name,
            "columns": columns,
            "indexes": indexes,
            "comment": table_comment,
        }

    def _parse_columns_from_string(self, column_section: str) -> List[Dict]:
        """Parse column definitions from string representation."""
        columns = []

        # Split by commas, but be careful about commas inside parentheses
        lines = column_section.split("\n")

        for line in lines:
            line = line.strip()
            # Skip non-column lines
            if self._is_non_column_line(line):
                continue

            # Extract column name and type using a more robust regex
            # Look for pattern: `column_name` type(parameters) or column_name
            # type(parameters)
            column_match = re.match(
                r'[`"]?(\w+)[`"]?\s+([^,\s(]+(?:\([^)]*\))?)', line)
            if column_match:
                column_name = column_match.group(1)
                column_type = self._extract_complete_column_type(
                    line, column_match.group(2))

                column_data = self._extract_column_attributes(
                    line, column_name, column_type)
                columns.append(column_data)

        return columns

    def _is_non_column_line(self, line: str) -> bool:
        """Check if a line is not a column definition."""
        return (
            not line
            or line.startswith("PRIMARY KEY")
            or line.startswith("UNIQUE KEY")
            or line.startswith("KEY")
            or line.startswith("FULLTEXT")
            or line.startswith("CONSTRAINT")
            or line.startswith("INDEX")
        )

    def _extract_complete_column_type(
            self, line: str, column_type: str) -> str:
        """Extract the complete column type, handling multi-line types."""
        # Handle special types that might be split across lines
        if column_type.startswith(
                "decimal(") and not column_type.endswith(")"):
            # Find the complete decimal type in the full line
            decimal_match = re.search(r"decimal\([^)]*\)", line)
            if decimal_match:
                return decimal_match.group(0)
        if column_type.startswith(
                "varchar(") and not column_type.endswith(")"):
            # Find the complete varchar type
            varchar_match = re.search(r"varchar\([^)]*\)", line)
            if varchar_match:
                return varchar_match.group(0)
        if column_type.startswith("int(") and not column_type.endswith(")"):
            # Find the complete int type
            int_match = re.search(r"int\([^)]*\)", line)
            if int_match:
                return int_match.group(0)

        return column_type

    def _extract_column_attributes(
            self, line: str, column_name: str, column_type: str) -> Dict:
        """Extract all column attributes from a line."""
        # Determine if nullable
        nullable = "NOT NULL" not in line.upper()

        # Check if primary key
        is_primary = "PRIMARY KEY" in line.upper()

        # Check if auto increment
        is_auto_increment = "AUTO_INCREMENT" in line.upper()

        # Extract default value
        default_value = self._extract_default_value(line)

        # Extract comment
        comment = self._extract_comment(line)

        return {
            "name": column_name,
            "type": column_type,
            "nullable": nullable,
            "is_primary": is_primary,
            "is_auto_increment": is_auto_increment,
            "default": default_value,
            "comment": comment,
        }

    def _extract_default_value(self, line: str) -> Optional[str]:
        """Extract default value from a column line."""
        default_match = re.search(
            r"DEFAULT\s+([^,\s]+(?:\([^)]*\))?)", line, re.IGNORECASE
        )
        if not default_match:
            return None

        default_value = default_match.group(1).strip("'")
        # Handle special cases
        if default_value.upper() == "NULL":
            return "NULL"
        if default_value.upper() == "CURRENT_TIMESTAMP":
            return "CURRENT_TIMESTAMP"

        return default_value

    def _extract_comment(self, line: str) -> str:
        """Extract comment from a column line."""
        comment_match = re.search(
            r"COMMENT\s+'([^']*)'", line, re.IGNORECASE)
        comment = comment_match.group(1) if comment_match else ""

        # Clean up comment (remove extra quotes if present)
        if comment.startswith("'") and comment.endswith("'"):
            comment = comment[1:-1]

        return comment

    def _extract_indexes_from_string(self, column_section: str) -> List[Dict]:
        """Extract index definitions from string representation."""
        indexes = []

        lines = column_section.split("\n")

        for line in lines:
            line = line.strip()

            # Primary key
            if line.startswith("PRIMARY KEY"):
                pk_match = re.search(
                    r"PRIMARY KEY\s*\(([^)]+)\)", line, re.IGNORECASE)
                if pk_match:
                    columns = [col.strip('`" ')
                               for col in pk_match.group(1).split(",")]
                    clean_columns = self._clean_index_columns(columns)
                    indexes.append(
                        {
                            "type": "PRIMARY KEY",
                            "columns": clean_columns,
                            "is_primary": True,
                            "name": "PRIMARY",
                        }
                    )

            # Unique key
            elif line.startswith("UNIQUE KEY"):
                unique_match = re.search(
                    r'UNIQUE KEY\s+[`"]?(\w+)[`"]?\s*\(([^)]+)\)', line, re.IGNORECASE
                )
                if unique_match:
                    name = unique_match.group(1)
                    columns = [
                        col.strip('`" ') for col in unique_match.group(2).split(",")
                    ]
                    clean_columns = self._clean_index_columns(columns)
                    indexes.append(
                        {"type": "UNIQUE", "columns": clean_columns, "name": name}
                    )

            # Regular key/index
            elif line.startswith("KEY") and not line.startswith("UNIQUE KEY"):
                key_match = re.search(
                    r'KEY\s+[`"]?(\w+)[`"]?\s*\(([^)]+)\)', line, re.IGNORECASE
                )
                if key_match:
                    name = key_match.group(1)
                    columns = [
                        col.strip('`" ') for col in key_match.group(2).split(",")
                    ]
                    clean_columns = self._clean_index_columns(columns)
                    indexes.append(
                        {"type": "INDEX", "columns": clean_columns, "name": name}
                    )

        return indexes

    def _clean_index_columns(self, columns: List[str]) -> List[str]:
        """Clean column names by removing type information and length specifications."""
        clean_columns = []
        for col in columns:
            # Handle MySQL index length specifications like `column_name`(200)
            # Pattern: column_name`(length (no closing paren) -> column_name
            clean_col = re.sub(
                r"([a-zA-Z_][a-zA-Z0-9_]*)`\([^)]*", r"\1", col
            )
            # Also handle cases with backticks around the whole
            # thing: `column_name`(length) -> column_name
            clean_col = re.sub(
                r"`([^`]+)`\([^)]*\)", r"\1", clean_col)
            # Also handle cases without backticks:
            # column_name(length) -> column_name
            clean_col = re.sub(
                r"([a-zA-Z_][a-zA-Z0-9_]*)\([^)]*\)", r"\1", clean_col
            )
            # Remove DESC or ASC modifiers
            clean_col = re.sub(r"\s+(DESC|ASC)\s*$", "", clean_col, flags=re.IGNORECASE)
            clean_col = clean_col.strip('`" ')
            if clean_col:
                clean_columns.append(clean_col)
        return clean_columns
