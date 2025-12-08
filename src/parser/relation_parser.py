"""
Relation Parser for GLPI Database Documentation Generator.

This module contains the RelationParser class for parsing GLPI relation constants
and converting them to DBML relationship definitions.

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
from pathlib import Path
from typing import Dict, List


class RelationParser:
    """Parser for GLPI relation constants file."""

    def __init__(self, relation_file_path: str):
        """Initialize the relation parser.

        Args:
            relation_file_path: Path to the relation constants PHP file
        """
        self.relation_file_path = Path(relation_file_path)
        self.relations = {}

    def parse(self) -> Dict:
        """Parse the relation constants file and extract relationships.

        Returns:
            Dictionary containing parsed relations
        """
        if not self.relation_file_path.exists():
            raise FileNotFoundError(
                f"Relation file not found: {self.relation_file_path}")

        with open(self.relation_file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract the $RELATION array - look for the array definition until the
        # first function or variable
        relation_match = re.search(
            r'\$RELATION\s*=\s*\[(.*?)(?=\n\s*\$|\n\s*function|\n\s*\/\/|\n\s*\?>|$)',
            content,
            re.DOTALL)
        if not relation_match:
            raise ValueError("Could not find $RELATION array in the file")

        relation_content = relation_match.group(1)

        # Parse the PHP array structure
        self.relations = self._parse_php_array(relation_content)

        return self.relations

    def _parse_php_array(self, content: str) -> Dict:
        """Parse PHP array structure and convert to Python dictionary.

        Args:
            content: The PHP array content as string

        Returns:
            Parsed relations as Python dictionary
        """
        relations = {}

        # Find all top-level keys in the array
        key_iter = re.finditer(r"'([^']+)'\s*=>\s*\[", content)
        for m in key_iter:
            key_name = m.group(1)

            # Check nesting level to ensure it's a top-level array
            prefix = content[:m.start()]
            nesting = prefix.count('[') - prefix.count(']')
            if nesting != 0:
                # This is an inner array (nested). Skip it for top-level
                # table extraction.
                continue

            # Find matching closing bracket for this '[' starting at m.end()-1
            start_idx = content.find('[', m.start())
            if start_idx == -1:
                continue

            depth = 0
            end_idx = None
            for i in range(start_idx, len(content)):
                ch = content[i]
                if ch == '[':
                    depth += 1
                elif ch == ']':
                    depth -= 1
                    if depth == 0:
                        end_idx = i
                        break

            if end_idx is None:
                # Unbalanced brackets — skip this key
                continue

            table_relations = content[start_idx + 1:end_idx]
            relations[key_name] = self._parse_table_relations(
                table_relations)

        return relations

    def _parse_table_relations(self, table_relations: str) -> List[Dict]:
        """Parse relations for a specific table.

        Args:
            table_relations: The relations content for one table

        Returns:
            List of relation dictionaries
        """
        relations = []

        # Find all relation entries: 'target_table' => 'foreign_key' or ['fk1',
        # 'fk2'] - handle both single and double quotes
        relation_entries = re.findall(
            r'["\']([^"\']+)["\']\s*=>\s*(?:["\']([^"\']+)["\']|\[(.*?)\])',
            table_relations
        )

        for target_table, single_fk, multiple_fks in relation_entries:
            if single_fk:
                # Simple foreign key relation
                relations.append({
                    'target_table': target_table,
                    'foreign_keys': [single_fk],
                    'is_polymorphic': False
                })
            elif multiple_fks:
                # Multiple foreign keys or polymorphic relation
                fk_list = self._parse_foreign_key_list(multiple_fks)
                is_polymorphic = self._is_polymorphic_relation(fk_list)
                relations.append({
                    'target_table': target_table,
                    'foreign_keys': fk_list,
                    'is_polymorphic': is_polymorphic
                })

        return relations

    def _parse_foreign_key_list(self, fk_content: str) -> List[str]:
        """Parse a list of foreign keys from PHP array format.

        Args:
            fk_content: Foreign key list content

        Returns:
            List of foreign key names
        """
        # Extract quoted strings from the array
        fk_matches = re.findall(r"'([^']+)'", fk_content)
        return fk_matches

    def _is_polymorphic_relation(self, foreign_keys: List[str]) -> bool:
        """Check if a relation is polymorphic (contains items_id and itemtype).

        Args:
            foreign_keys: List of foreign key names

        Returns:
            True if the relation is polymorphic
        """
        return 'items_id' in foreign_keys and 'itemtype' in foreign_keys

    def _normalize_table_name(self, table_name: str) -> str:
        """Normalize table name by removing '_' prefix if it exists.

        Args:
            table_name: Table name to normalize

        Returns:
            Normalized table name
        """
        return table_name[1:] if table_name.startswith('_') else table_name

    def get_dbml_relations(self) -> List[Dict]:
        """Convert parsed relations to DBML format.

        Returns:
            List of DBML relation dictionaries
        """
        dbml_relations = []

        for source_table, table_relations in self.relations.items():
            for relation in table_relations:
                target_table = relation['target_table']
                foreign_keys = relation['foreign_keys']
                is_polymorphic = relation['is_polymorphic']

                # Skip polymorphic relations for now as they're complex to
                # represent in DBML
                if is_polymorphic:
                    continue

                # For simple foreign key relations, create DBML ref
                # We want the DBML `Ref` to have the table containing the
                # foreign key on the left and the referenced table (usually
                # with primary key `id`) on the right. In our parsed structure
                # `source_table` is the outer key from the PHP array (the
                # referenced table) and `target_table` is the inner key (the
                # table that contains the foreign key columns). To produce
                # DBML like `appliances.users_id > users.id` we set the
                # left-hand side (source_table) to the table with the FK.
                if len(foreign_keys) == 1:
                    dbml_relations.append({
                        'source_table': target_table,  # Table with foreign key
                        'target_table': source_table,  # Referenced table
                        'source_column': foreign_keys[0],  # Foreign key column
                        'target_column': 'id',  # PK of referenced table
                        'relation_type': '1:n'  # One-to-many relationship
                    })
                elif len(foreign_keys) == 2:
                    # Handle composite foreign keys (simplified)
                    dbml_relations.append({
                        'source_table': target_table,  # Table with foreign keys
                        'target_table': source_table,  # Referenced table
                        # Assuming both reference id on referenced table
                        'source_columns': foreign_keys,  # Foreign key columns
                        'target_columns': ['id', 'id'],
                        'relation_type': 'm:n'
                    })

        return dbml_relations

    def get_polymorphic_relations(self) -> List[Dict]:
        """Get polymorphic relations for documentation purposes.

        Returns:
            List of polymorphic relation dictionaries
        """
        polymorphic_relations = []

        for source_table, table_relations in self.relations.items():
            for relation in table_relations:
                if relation['is_polymorphic']:
                    polymorphic_relations.append({
                        'source_table': source_table,
                        'target_table': relation['target_table'],
                        'foreign_keys': relation['foreign_keys'],
                        'description': 'Polymorphic relation using items_id and itemtype'
                    })

        return polymorphic_relations

    def get_all_relations_for_table(self, table_name: str) -> List[Dict]:
        """Get all relations for a specific table (both incoming and outgoing).

        Args:
            table_name: Name of the table to get relations for

        Returns:
            List of all relations involving this table
        """
        all_relations = []

        # Normalize table name
        normalized_table = self._normalize_table_name(table_name)

        # Check outgoing relations (this table references others)
        if table_name in self.relations:
            for relation in self.relations[table_name]:
                all_relations.append({
                    'type': 'outgoing',
                    'source_table': table_name,
                    'target_table': relation['target_table'],
                    'foreign_keys': relation['foreign_keys'],
                    'is_polymorphic': relation['is_polymorphic']
                })

        # Check incoming relations (other tables reference this table)
        for source_table, table_relations in self.relations.items():
            for relation in table_relations:
                if self._normalize_table_name(
                        relation['target_table']) == normalized_table:
                    all_relations.append({
                        'type': 'incoming',
                        'source_table': source_table,
                        'target_table': relation['target_table'],
                        'foreign_keys': relation['foreign_keys'],
                        'is_polymorphic': relation['is_polymorphic']
                    })

        return all_relations
