# GLPI Database Documentation Generator

Generate and publish GLPI database schema documentation to dbdocs.io.

## Installation

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

For publishing: install [dbdocs CLI](https://docs.dbdocs.io/#dbdocs-cli-guide)

## Usage

### Single file

```bash
python glpi_dbdocs.py generate --sql-file path/to/glpi.sql --output docs
```

With relations:
```bash
python glpi_dbdocs.py generate --sql-file path/to/glpi.sql --relation-file path/to/relation.constant.php --output docs
```

### Multiple sources

1. Copy configuration:
   ```bash
   cp config.example.yml config.yml
   ```

2. Process all sources:
   ```bash
   python glpi_dbdocs.py process
   ```

3. Publish:
   ```bash
   python glpi_dbdocs.py publish
   ```

## License

GNU GPLv3+
