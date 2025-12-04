import click
import yaml
import json
from jsonschema import validate, ValidationError
from deepdiff import DeepDiff
from pathlib import Path

CONFIG_DIR = Path("configs")
SCHEMA_FILE = Path("schemas/config_schema.json")
GENERATED_DIR = Path("generated_configs")
ENVIRONMENTS = ["dev", "staging", "prod"]

def deep_merge(source, destination):
    """
    Deeply merges two dictionaries. Arrays are merged based on a 'name' key.
    """
    for key, value in source.items():
        if isinstance(value, dict):
            node = destination.setdefault(key, {})
            deep_merge(value, node)
        elif isinstance(value, list):
            dest_list = destination.setdefault(key, [])
            for item in value:
                if isinstance(item, dict) and 'name' in item:
                    # Find and update item in destination list by name
                    dest_item = next((i for i in dest_list if i.get('name') == item['name']), None)
                    if dest_item:
                        deep_merge(item, dest_item)
                    else:
                        dest_list.append(item)
                else:
                    # Simple append for lists without named items
                    if item not in dest_list:
                        dest_list.append(item)
        else:
            destination[key] = value
    return destination

def load_config(env):
    """Loads and merges configuration for a given environment."""
    if env not in ENVIRONMENTS:
        raise click.ClickException(f"Invalid environment '{env}'. Must be one of {ENVIRONMENTS}")

    base_config_path = CONFIG_DIR / "base.yaml"
    env_config_path = CONFIG_DIR / f"{env}.yaml"

    with open(base_config_path, 'r') as f:
        config = yaml.safe_load(f) or {}

    if env_config_path.exists():
        with open(env_config_path, 'r') as f:
            env_config = yaml.safe_load(f) or {}
            config = deep_merge(env_config, config)
    
    return config

def validate_config(config, env):
    """Validates the configuration against the JSON schema and custom rules."""
    # 1. JSON Schema Validation
    with open(SCHEMA_FILE, 'r') as f:
        schema = json.load(f)
    try:
        validate(instance=config, schema=schema)
    except ValidationError as e:
        raise click.ClickException(f"Schema validation failed for '{env}': {e.message}")

    # 2. Custom Validation Rules
    if env == "prod":
        for db in config.get("databases", []):
            if db.get("publicly_accessible"):
                raise click.ClickException(f"Validation Error in '{env}': Production database '{db['name']}' cannot be publicly accessible.")
            if db.get("backup_retention_period", 0) < 30:
                raise click.ClickException(f"Validation Error in '{env}': Production database '{db['name']}' backup retention must be >= 30 days.")

    click.secho(f"Configuration for '{env}' is valid.", fg="green")

@click.group()
def cli():
    """A CLI tool to manage multi-environment configurations."""
    pass

@cli.command()
@click.argument("environments", nargs=-1)
def validate(environments):
    """Validates configurations for one or more environments."""
    if not environments:
        environments = ENVIRONMENTS
    
    for env in environments:
        try:
            config = load_config(env)
            validate_config(config, env)
        except Exception as e:
            click.secho(str(e), fg="red")
            continue

@cli.command()
@click.argument("env", type=click.Choice(ENVIRONMENTS))
def generate(env):
    """Generates a .tfvars.json file for a specific environment."""
    try:
        config = load_config(env)
        validate_config(config, env)

        GENERATED_DIR.mkdir(exist_ok=True)
        output_path = GENERATED_DIR / f"{env}.tfvars.json"

        with open(output_path, 'w') as f:
            json.dump(config, f, indent=2)

        click.secho(f"Successfully generated '{output_path}' for '{env}'.", fg="green")
    except Exception as e:
        click.secho(str(e), fg="red")

@cli.command()
@click.argument("env1", type=click.Choice(ENVIRONMENTS))
@click.argument("env2", type=click.Choice(ENVIRONMENTS))
def diff(env1, env2):
    """Shows the difference between two environments."""
    try:
        config1 = load_config(env1)
        config2 = load_config(env2)

        diff = DeepDiff(config1, config2, ignore_order=True, view='tree')

        if not diff:
            click.secho(f"No differences found between '{env1}' and '{env2}'.", fg="yellow")
            return

        click.secho(f"Differences between '{env1}' (left) and '{env2}' (right):", bold=True)
        for change in diff:
            # Use a helper to format the path from DeepDiff
            path_str = "".join([f"['{p}']" for p in change.path()])
            if change.t1 is not None and change.t2 is not None:
                click.echo(f"~ {path_str}: {click.style(str(change.t1), fg='red')} -> {click.style(str(change.t2), fg='green')}")

    except Exception as e:
        click.secho(str(e), fg="red")

if __name__ == "__main__":
    cli()