"""
DBDocs Publisher for GLPI Database Documentation Generator.

This module handles publishing database documentation to dbdocs.io.

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

import subprocess
from pathlib import Path
from typing import Dict, List

import click


class DBDocsPublisher:
    """Handles publishing database documentation to dbdocs.io."""

    def __init__(self, dbdocs_cli: str = "dbdocs"):
        self.dbdocs_cli = dbdocs_cli

    def publish_project(self, dbml_file: str, project_name: str) -> bool:
        """
        Publish a single project to dbdocs.io.

        Args:
            dbml_file: Path to the DBML file
            project_name: Name of the project on dbdocs.io

        Returns:
            bool: True if successful, False otherwise
        """
        dbml_path = Path(dbml_file)

        if not dbml_path.exists():
            click.echo(f"Error: DBML file not found: {dbml_file}")
            return False

        try:
            click.echo(f"Publishing {project_name} to dbdocs.io...")

            # Build the dbdocs command
            cmd = [
                self.dbdocs_cli, "build", str(dbml_path),
                "--project", project_name
            ]

            # Execute the command
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )

            click.echo(f"✅ Successfully published {project_name} to dbdocs.io")
            return True

        except subprocess.CalledProcessError as e:
            click.echo(f"❌ Error publishing {project_name}: {e}")
            if e.stdout:
                click.echo(f"stdout: {e.stdout}")
            if e.stderr:
                click.echo(f"stderr: {e.stderr}")
            return False
        except FileNotFoundError:
            click.echo(f"❌ Error: {self.dbdocs_cli} command not found. "
                       "Please install dbdocs CLI first.")
            return False

    def publish_all_projects(self, projects: List[Dict]) -> Dict[str, bool]:
        """
        Publish multiple projects to dbdocs.io.

        Args:
            projects: List of project configurations

        Returns:
            Dict[str, bool]: Results for each project
        """
        results = {}

        for project in projects:
            dbml_file = project.get("dbml_file")
            project_name = project.get("project_name")

            if not dbml_file or not project_name:
                click.echo(
                    f"⚠️  Skipping project with missing configuration: {project}")
                results[project_name or "unknown"] = False
                continue

            success = self.publish_project(dbml_file, project_name)
            results[project_name] = success

        return results

    def check_dbdocs_installed(self) -> bool:
        """Check if dbdocs CLI is installed and available."""
        try:
            subprocess.run(
                [self.dbdocs_cli, "--version"],
                capture_output=True,
                check=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
