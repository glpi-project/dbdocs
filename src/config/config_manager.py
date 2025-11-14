"""
Configuration Manager for GLPI Database Documentation Generator.

This module handles loading and managing configuration from YAML files.

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

import click
import yaml


class ConfigManager:
    """Manages configuration for the GLPI database documentation generator."""

    def __init__(self, config_file: str = "config.yml"):
        self.config_file = Path(config_file)
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        """Load configuration from YAML file."""
        if not self.config_file.exists():
            raise click.ClickException(
                f"Configuration file not found: {self.config_file}. "
                "Please copy config.example.yml to config.yml and customize it."
            )

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise click.ClickException(
                f"Error parsing configuration file: {e}")

    def get_global_settings(self) -> Dict:
        """Get global settings from configuration."""
        return self.config.get("global", {})

    def get_sources(self) -> List[Dict]:
        """Get list of database sources from configuration."""
        return self.config.get("sources", [])

    def get_publish_settings(self) -> Dict:
        """Get publish settings from configuration."""
        return self.config.get("publish", {})

    def get_source_by_name(self, name: str) -> Optional[Dict]:
        """Get a specific source configuration by name."""
        for source in self.get_sources():
            if source.get("name") == name:
                return source
        return None

    def get_output_dir(self) -> str:
        """Get the output directory from global settings."""
        return self.get_global_settings().get("output_dir", "docs")

    def is_auto_publish_enabled(self) -> bool:
        """Check if auto-publish is enabled."""
        return self.get_publish_settings().get("auto_publish", False)

    def get_dbdocs_cli(self) -> str:
        """Get the dbdocs CLI command."""
        return self.get_publish_settings().get("dbdocs_cli", "dbdocs")
