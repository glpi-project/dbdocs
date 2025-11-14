"""
CLI Commands for GLPI Database Documentation Generator.

This module contains the Click command-line interface for the GLPI database documentation tool.

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

import click

from ..parser import GLPIDatabaseParser, RelationParser
from ..generator import DBDocsGenerator
from ..config import ConfigManager
from ..publisher import DBDocsPublisher


@click.group()
def cli():
    """GLPI Database Documentation Generator CLI."""


@cli.command()
@click.option(
    "--sql-file", "-s", required=True, help="Path to GLPI SQL installation file"
)
@click.option(
    "--relation-file", "-r", help="Path to GLPI relation constants PHP file"
)
@click.option(
    "--output",
    "-o",
    default="docs",
    help="Output directory for generated documentation",
)
@click.option(
    "--output-file",
    "-f",
    help="Output filename (default: dbdocs.dbml)",
)
def generate(sql_file: str, relation_file: str, output: str, output_file: str):
    """
    Generate database documentation from SQL file.

    This command parses a single SQL file and generates dbdocs-compatible documentation.
    """
    try:
        # Parse SQL file
        click.echo(f"Parsing SQL file: {sql_file}")
        parser = GLPIDatabaseParser(sql_file)
        tables = parser.parse_sql_file()

        if not tables:
            click.echo("No tables found in SQL file")
            return

        click.echo(f"Found {len(tables)} tables")

        # Parse relations file if provided
        relations = []
        if relation_file:
            click.echo(f"Parsing relation file: {relation_file}")
            relation_parser = RelationParser(relation_file)
            relation_parser.parse()  # Parse but don't store result
            relations = relation_parser.get_dbml_relations()
            click.echo(f"Found {len(relations)} relations")

        # Generate dbdocs documentation
        click.echo("Generating dbdocs documentation...")
        generator = DBDocsGenerator(tables, relations)

        if output_file:
            # Save to specific file
            output_path = Path(output)
            output_path.mkdir(parents=True, exist_ok=True)
            dbml_content = generator.generate_dbdocs_dbml()

            output_file_path = output_path / output_file
            with open(output_file_path, "w", encoding="utf-8") as f:
                f.write(dbml_content)

            click.echo(f"Generated documentation: {output_file_path}")
        else:
            # Use default behavior
            generator.save_dbdocs_file(output)

    except Exception as e:
        raise click.ClickException(f"Error: {str(e)}")


def _validate_source_config(source_config):
    """Validate source configuration and return extracted values."""
    name = source_config.get("name", "unknown")
    sql_file = source_config.get("sql_file")
    relation_file = source_config.get("relation_file")
    output_file = source_config.get("output_file", f"{name}.dbml")
    project_name = source_config.get("project_name")
    description = source_config.get("description", "")

    click.echo(f"\n📋 Processing source: {name}")
    if description:
        click.echo(f"   Description: {description}")

    if not sql_file:
        click.echo(f"⚠️  Skipping {name}: no SQL file specified")
        return None

    if not Path(sql_file).exists():
        click.echo(f"⚠️  Skipping {name}: SQL file not found: {sql_file}")
        return None

    return {
        "name": name,
        "sql_file": sql_file,
        "relation_file": relation_file,
        "output_file": output_file,
        "project_name": project_name
    }


def _parse_relations(relation_file):
    """Parse relations file and return relations list."""
    relations = []
    if relation_file:
        if not Path(relation_file).exists():
            click.echo(f"⚠️  Relation file not found: {relation_file}")
        else:
            click.echo(f"   Parsing relations from: {relation_file}")
            relation_parser = RelationParser(relation_file)
            relation_parser.parse()  # Parse but don't store result
            relations = relation_parser.get_dbml_relations()
            click.echo(f"   Found {len(relations)} relations")
    return relations


def _process_single_source(source_config, output_dir):
    """Process a single source configuration."""
    # Validate and extract configuration
    config = _validate_source_config(source_config)
    if not config:
        return None

    # Parse SQL file
    parser = GLPIDatabaseParser(config["sql_file"])
    tables = parser.parse_sql_file()

    if not tables:
        click.echo(f"⚠️  No tables found in {config['sql_file']}")
        return None

    click.echo(f"   Found {len(tables)} tables")

    # Parse relations
    relations = _parse_relations(config["relation_file"])

    # Generate and save DBML
    generator = DBDocsGenerator(tables, relations)
    dbml_content = generator.generate_dbdocs_dbml()

    output_path = Path(output_dir) / config["output_file"]
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(dbml_content)

    click.echo(f"✅ Generated: {output_path}")

    # Return project info for potential auto-publish
    if config["project_name"]:
        return {
            "dbml_file": str(output_path),
            "project_name": config["project_name"],
            "name": config["name"]
        }
    return None


@cli.command()
@click.option(
    "--config", "-c", default="config.yml", help="Configuration file path"
)
@click.option(
    "--source", "-s", help="Process only specific source by name"
)
def process(config: str, source: str):
    """
    Process multiple database sources from configuration file.

    This command processes all sources defined in the configuration file,
    or a specific source if --source is provided.
    """
    try:
        # Load configuration
        config_manager = ConfigManager(config)

        # Get sources to process
        if source:
            sources = [config_manager.get_source_by_name(source)]
            if not sources[0]:
                raise click.ClickException(
                    f"Source '{source}' not found in configuration")
        else:
            sources = config_manager.get_sources()

        if not sources:
            click.echo("No sources found in configuration")
            return

        output_dir = config_manager.get_output_dir()
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        processed_projects = []

        # Process each source
        for source_config in sources:
            if not source_config:
                continue

            project_info = _process_single_source(source_config, output_dir)
            if project_info:
                processed_projects.append(project_info)

        # Auto-publish if enabled
        if config_manager.is_auto_publish_enabled() and processed_projects:
            click.echo("\n🚀 Auto-publishing enabled, publishing projects...")
            publisher = DBDocsPublisher(config_manager.get_dbdocs_cli())
            publisher.publish_all_projects(processed_projects)

    except Exception as e:
        raise click.ClickException(f"Error: {str(e)}")


def _publish_specific_file(dbml_file, project_name):
    """Publish a specific DBML file."""
    publisher = DBDocsPublisher()
    if publisher.publish_project(dbml_file, project_name):
        click.echo("✅ Publication successful")
    else:
        click.echo("❌ Publication failed")


def _publish_specific_project(config_manager, project, publisher):
    """Publish a specific project from configuration."""
    source_config = config_manager.get_source_by_name(project)
    if not source_config:
        raise click.ClickException(
            f"Project '{project}' not found in configuration")

    project_name = source_config.get("project_name")
    output_file = source_config.get("output_file", f"{project}.dbml")
    output_path = Path(config_manager.get_output_dir()) / output_file

    if not output_path.exists():
        raise click.ClickException(f"DBML file not found: {output_path}")

    if publisher.publish_project(str(output_path), project_name):
        click.echo("✅ Publication successful")
    else:
        click.echo("❌ Publication failed")


def _publish_all_projects(config_manager, publisher):
    """Publish all projects from configuration."""
    sources = config_manager.get_sources()
    projects = []

    for source in sources:
        project_name = source.get("project_name")
        output_file = source.get("output_file", f"{source['name']}.dbml")
        output_path = Path(config_manager.get_output_dir()) / output_file

        if output_path.exists() and project_name:
            projects.append({
                "dbml_file": str(output_path),
                "project_name": project_name
            })

    if not projects:
        click.echo("No projects found to publish")
        return

    click.echo(f"Publishing {len(projects)} projects...")
    results = publisher.publish_all_projects(projects)

    # Summary
    successful = sum(1 for success in results.values() if success)
    total = len(results)
    click.echo(f"\n📊 Publication summary: {successful}/{total} successful")


@cli.command()
@click.option(
    "--config", "-c", default="config.yml", help="Configuration file path"
)
@click.option(
    "--project", "-p", help="Publish only specific project by name"
)
@click.option(
    "--dbml-file", "-f", help="Publish specific DBML file"
)
@click.option(
    "--project-name", help="Project name for dbdocs.io (when using --dbml-file)"
)
def publish(config: str, project: str, dbml_file: str, project_name: str):
    """
    Publish database documentation to dbdocs.io.

    This command can publish:
    - All projects from configuration file
    - A specific project from configuration
    - A specific DBML file with project name
    """
    try:
        if dbml_file and project_name:
            # Publish specific file
            _publish_specific_file(dbml_file, project_name)
            return

        # Load configuration for other cases
        config_manager = ConfigManager(config)
        publisher = DBDocsPublisher(config_manager.get_dbdocs_cli())

        # Check if dbdocs CLI is available
        if not publisher.check_dbdocs_installed():
            click.echo("❌ dbdocs CLI not found. Please install it first.")
            return

        if project:
            # Publish specific project from config
            _publish_specific_project(config_manager, project, publisher)
        else:
            # Publish all projects from config
            _publish_all_projects(config_manager, publisher)

    except Exception as e:
        raise click.ClickException(f"Error: {str(e)}")
