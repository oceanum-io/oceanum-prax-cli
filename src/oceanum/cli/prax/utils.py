
import click

from oceanum.cli.symbols import wrn, chk, info

from .models import ErrorResponse, ProjectSpec, SecretData, ResourcePermissionsSchema, PermissionsSchema

def format_run_status(status: str) -> str:
    status = status.lower()
    if status == 'pending':
        return click.style(status.upper(), fg='white')
    elif status == 'running':
        return click.style(status.upper(), fg='cyan')
    elif status == 'succeeded':
        return click.style(status.upper(), fg='green')
    elif status == 'failed':
        return click.style(status.upper(), fg='red')
    elif status == 'error':
        return click.style(status.upper(), fg='red')
    else:
        return status

def format_route_status(status: str) -> str:
    if status == 'online':
        return click.style(status.upper(), fg='green')
    elif status == 'offline':
        return click.style(status.upper(), fg='black')
    elif status == 'pending':
        return click.style(status.upper(), fg='yellow')
    elif status == 'starting':
        return click.style(status.upper(), fg='cyan')
    elif status == 'error':
        return click.style(status.upper(), fg='red', bold=True)
    else:
        return status
    

def project_status_color(status: str) -> str:
    if status == 'ready':
        return click.style(status.upper(), fg='green')
    elif status == 'degraded':
        return click.style(status.upper(), fg='yellow')
    elif status == 'updating':
        return click.style(status.upper(), fg='cyan')
    elif status == 'error':
        return click.style(status.upper(), fg='red')
    else:
        return click.style(status.upper(), fg='white')
        
def stage_status_color(stage: dict) -> str:
    if stage['status'] == 'healthy':
        return click.style(stage['name'], fg='green')
    elif stage['status'] == 'degraded':
        return click.style(stage['name'], fg='yellow')
    elif stage['status'] == 'error':
        return click.style(stage['name'], fg='red')
    elif stage['status'] == 'updating':
        return click.style(stage['name'], fg='cyan')
    else:
        return stage['name']
    

def source_status_color(status: str) -> str:
    if status == 'connected':
        return click.style(status.upper(), fg='green')
    elif status == 'disconnected':
        return click.style(status.upper(), fg='red')
    elif status == 'pending':
        return click.style(status.upper(), fg='yellow')
    elif status == 'forbidden':
        return click.style(status.upper(), fg='red')
    return click.style(status.upper(), fg='white')


def echoerr(error: ErrorResponse):
    if isinstance(error.detail, dict):
        for key, value in error.detail.items():
            click.echo(f" {wrn} {key}: {value}")
    elif isinstance(error.detail, list):
        for item in error.detail:
            click.echo(f" {wrn} {item}")
    elif isinstance(error.detail, str):
        click.echo(f" {wrn} {error.detail}")
    elif error.detail is None:
        click.echo(f" {wrn} No error message provided!")

def parse_secrets(secrets: list) -> list[dict]:
    parsed_secrets = []
    for secret in secrets:
        secret_name, secret_data = secret.split(':')
        secret_data = dict([s.split('=') for s in secret_data.split(',')])
        secret_dict = {'name': secret_name, 'data': secret_data}
        parsed_secrets.append(secret_dict)
    return parsed_secrets


def merge_secrets(project_spec: ProjectSpec, secrets: list[str]) -> ProjectSpec:
    for secret in parse_secrets(secrets):
        if project_spec.resources is not None:
            if secret['name'] not in [s.name for s in project_spec.resources.secrets]:
                raise Exception(f"Secret '{secret['name']}' not found in project spec!")
            for existing_secret in project_spec.resources.secrets:
                if existing_secret.name == secret['name']:
                    if isinstance(existing_secret.data, SecretData):
                        if existing_secret.data.root is None:
                            existing_secret.data.root = secret['data']
                        else:
                            existing_secret.data.root.update(secret['data'])
                    else:
                        existing_secret.data.update(secret['data'])
    return project_spec


def format_permissions_display(permissions: ResourcePermissionsSchema, resource_name: str, resource_type: str = "resource") -> None:
    """
    Display resource permissions in a nice, readable format.
    
    Args:
        permissions: The ResourcePermissionsSchema object to display
        resource_name: Name of the resource (e.g., project name, route name)
        resource_type: Type of resource (e.g., "project", "route")
    """
    def format_permission_value(value: bool | None) -> str:
        if value is True:
            return click.style("✓", fg='green', bold=True)
        elif value is False:
            return click.style("✗", fg='red', bold=True)
        else:
            return click.style("−", fg='yellow')
    
    def display_permissions_table(perms_list: list[PermissionsSchema], title: str):
        if not perms_list:
            click.echo(f"    No {title.lower()} permissions set")
            return
            
        click.echo(f"    {click.style(title + ':', fg='blue', bold=True)}")
        click.echo()
        
        # Table header
        click.echo(click.style(f"    {'Subject':<30} {'View':<6} {'Change':<8} {'Delete':<8} {'Assign':<6}", bold=True))
        click.echo(click.style("    " + "─" * 60, dim=True))
        
        # Table rows
        for perm in perms_list:
            subject = perm.subject[:28] + ".." if len(perm.subject) > 30 else perm.subject
            
            # Use fixed positions instead of string formatting for styled text
            parts = [
                f"    {subject:<30}",
                f"  {format_permission_value(perm.view)}     ", # View column (6 chars)
                f"  {format_permission_value(perm.change)}      ", # Change column (8 chars)  
                f"  {format_permission_value(perm.delete)}      ", # Delete column (8 chars)
                f"  {format_permission_value(perm.assign)}"      # Assign column (6 chars)
            ]
            
            click.echo("".join(parts))
        click.echo()
    
    click.echo(f" {chk} Permissions for {resource_type} '{resource_name}' updated successfully!")
    click.echo()
    click.echo(f" {info} Current permissions:")
    click.echo()
    
    # Display users permissions
    display_permissions_table(permissions.users, "Users")
    
    # Display groups permissions  
    display_permissions_table(permissions.groups, "Groups")
    
    if not permissions.users and not permissions.groups:
        click.echo("    No permissions currently set for this resource.")
        click.echo()
    
    # Legend
    click.echo("    " + click.style("Legend:", fg='cyan', bold=True))
    click.echo(f"    {format_permission_value(True)} = Granted   {format_permission_value(False)} = Denied   {format_permission_value(None)} = Not set")
    click.echo()
