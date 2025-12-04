import click
import yaml
import json
from jsonschema import validate as jsonschema_validate, ValidationError
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
        jsonschema_validate(instance=config, schema=schema)
    except ValidationError as e:
        # Format the path to be more readable, e.g., "compute_instances[0].replicas"
        path = ".".join(str(p) for p in e.path)
        raise click.ClickException(f"Schema validation failed for '{env}' at '{path}': {e.message}")

    # 2. Custom Validation Rules
    # Rule: Ensure attached security groups are actually defined (Cross-resource validation)
    defined_sec_groups = {sg['name'] for sg in config.get("security_groups", [])}

    for instance in config.get("compute_instances", []):
        attached_sgs = instance.get("security_groups", [])
        if not attached_sgs:
            raise click.ClickException(f"Validation Error in '{env}': Instance '{instance['name']}' must have at least one security group.")
        for attached_sg in attached_sgs:
            if attached_sg not in defined_sec_groups:
                raise click.ClickException(f"Validation Error in '{env}': Instance '{instance['name']}' uses undefined security group '{attached_sg}'.")

    # Rule: Enforce cheaper instance types in 'dev' (Environment-specific policy)
    if env == "dev":
        allowed_dev_types = ["t3.micro", "t3.small"]
        for instance in config.get("compute_instances", []):
            if instance.get("instance_type") not in allowed_dev_types:
                raise click.ClickException(f"Validation Error in '{env}': Instance '{instance['name']}' has type '{instance.get('instance_type')}'. Must be one of {allowed_dev_types}.")

    # Rule: Production-specific hardening
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

        # Helper to format the path from DeepDiff for readability
        def format_path(path_obj):
            return path_obj.replace("root", "").replace("'", "")

        if 'values_changed' in diff:
            for item in diff['values_changed']:
                path = format_path(item.path())
                click.secho(f"~ Modified: {path}", fg='yellow', nl=False)
                click.echo(f" from {click.style(str(item.t1), fg='red')} to {click.style(str(item.t2), fg='green')}")
        if 'iterable_item_added' in diff:
            for item in diff['iterable_item_added']:
                click.secho(f"+ Added:    {format_path(item.path())} with value {item.t2}", fg='green')
        if 'iterable_item_removed' in diff:
            for item in diff['iterable_item_removed']:
                click.secho(f"- Removed:  {format_path(item.path())} with value {item.t1}", fg='red')

    except Exception as e:
        click.secho(str(e), fg="red")

if __name__ == "__main__":
    cli()