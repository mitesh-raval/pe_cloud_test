Multi-Environment Configuration Management System

This tool provides a simple yet powerful way to manage infrastructure and application configurations across multiple environments (dev, staging, prod). It helps prevent manual errors by using structured, version-controlled configuration files with built-in validation and templating.

## Design Decisions

*   **Configuration Format**: YAML was chosen for its human-readability and support for comments, making it ideal for configuration files.
*   **Inheritance Model**: A simple override system is used. A `base.yaml` file defines common defaults, and environment-specific files (`dev.yaml`, `prod.yaml`) override these defaults. The merge logic is name-based for lists of objects, allowing granular updates.
*   **Validation**: Validation is two-fold:
    1.  **Schema Validation**: `jsonschema` enforces the fundamental structure, data types, and allowed values. This is fast and declarative.
    2.  **Custom Rules**: Python functions implement environment-specific logic (e.g., "production databases cannot be public"). This makes the validation layer extensible.
*   **CLI Framework**: `click` is used to create a clean, user-friendly command-line interface. It simplifies argument parsing and provides helpful feedback.
*   **Output Format**: The tool generates `.tfvars.json` files. This format is directly consumable by Terraform (`terraform apply -var-file="prod.tfvars.json"`), bridging the gap between configuration management and infrastructure provisioning.

## How to Run

### 1. Setup

First, install the required Python packages:

```bash
pip install -r requirements.txt
```

### 2. Validate Configurations

To validate the configuration for a specific environment or all environments:

```bash
# Validate the 'prod' environment
python config_manager.py validate prod

# Validate 'dev' and 'staging'
python config_manager.py validate dev staging
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
# Show differences between staging and prod
python config_manager.py diff staging prod
```

## Potential Extensions

*   **Dynamic Backends**: Store configuration files in a Git repository or an S3 bucket instead of the local filesystem.
*   **Secrets Management**: Integrate with a secrets manager like HashiCorp Vault or AWS Secrets Manager to inject sensitive values at runtime.
*   **More Complex Validation**: Implement cross-resource validation (e.g., ensure a compute instance's security group is defined elsewhere in the config).
*   **Drift Detection**: Add a command to compare the generated configuration against the actual state of the deployed infrastructure (requires cloud provider SDKs).
*   **Plugin Architecture**: Allow new resource types and validation rules to be added as plugins without modifying the core tool.
