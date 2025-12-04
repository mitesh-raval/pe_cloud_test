# Multi-Environment Configuration Management System

This tool provides a simple yet powerful way to manage infrastructure and application configurations across multiple environments (dev, staging, prod). It helps prevent manual errors by using structured, version-controlled configuration files with built-in validation and templating.

## Project Structure

```
.
├── configs/              # Environment-specific YAML files (base.yaml, prod.yaml, etc.)
├── generated_configs/    # Output directory for generated .tfvars.json files
├── schemas/              # Contains the JSON schema for configuration validation
├── config_manager.py     # The core CLI tool
└── README.md
```

## Design Decisions

*   **Configuration Format**: YAML was chosen for its human-readability and support for comments, making it ideal for configuration files.
*   **Inheritance Model**: A simple override system is used. A `base.yaml` file defines common defaults, and environment-specific files (`dev.yaml`, `prod.yaml`) override these defaults. The merge logic is name-based for lists of objects, allowing granular updates.
*   **Validation**: Validation is two-fold:
    1.  **Schema Validation**: `jsonschema` (using `schemas/config_schema.json`) enforces the fundamental structure, data types, and allowed values. This is fast and declarative.
    2.  **Custom Rules**: Python functions implement environment-specific logic (e.g., "production databases cannot be public"). This makes the validation layer extensible.
*   **CLI Framework**: `click` is used to create a clean, user-friendly command-line interface. It simplifies argument parsing and provides helpful feedback to the user.
*   **Output Format**: The tool generates `.tfvars.json` files. This format is directly consumable by Terraform (`terraform apply -var-file="prod.tfvars.json"`), bridging the gap between configuration management and infrastructure provisioning.

## How to Run

### 1. Setup

**Prerequisites:**
*   Python 3.8+
*   pip

**Installation:**
First, install the required Python packages:

```bash
pip install -r requirements.txt
```

### 2. Validate Configurations

To validate the configuration for a specific environment or all environments:

```bash
# Validate a single environment
python config_manager.py validate prod
# On success: Configuration for 'prod' is valid.

# Validate 'dev' and 'staging'
python config_manager.py validate dev staging

# Validate all environments
python config_manager.py validate
# On failure: Schema validation failed for 'dev' at 'compute_instances.0.instance_type': 't3.large' is not one of ['t3.micro', 't3.small']
```

### 3. Generate Terraform Variables

To generate a `.tfvars.json` file for an environment:

```bash
# Generate config for dev
python config_manager.py generate dev

# Generate config for prod
python config_manager.py generate prod
```

This will create a file like `generated_configs/prod.tfvars.json` with the fully merged and validated configuration.

### 4. Show Differences Between Environments

To see what differs between any two environments:

```bash
# Show differences between dev and staging
python config_manager.py diff dev staging 

# Example output
Differences between 'dev' (left) and 'staging' (right):
~ Modified: [compute_instances][0][replicas] from 1 to 2
~ Modified: [databases][0][backup_retention_period] from 7 to 15
+ Added:    [compute_instances][0][security_groups][1] with value staging-web-sg
+ Added:    [security_groups][1] with value {'name': 'staging-web-sg', 'description': 'Allow web traffic from corporate VPN', 'rules': [{'protocol': 'tcp', 'from_port': 80, 'to_port': 80, 'cidr_blocks': ['10.100.0.0/16']}, {'protocol': 'tcp', 'from_port': 443, 'to_port': 443, 'cidr_blocks': ['10.100.0.0/16']}]}
```

## Potential Extensions

*   **Dynamic Backends**: Store configuration files in a Git repository or an S3 bucket instead of the local filesystem.
*   **Secrets Management**: Integrate with a secrets manager like HashiCorp Vault or AWS Secrets Manager to inject sensitive values at runtime.
*   **Drift Detection**: Add a command to compare the generated configuration against the actual state of the deployed infrastructure (requires cloud provider SDKs).
*   **Plugin Architecture**: Allow new resource types and validation rules to be added as plugins without modifying the core tool.
