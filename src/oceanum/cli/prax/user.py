import os
import click

from oceanum.cli.renderer import Renderer, RenderField
from oceanum.cli.symbols import err, chk, wrn
from oceanum.cli.auth import login_required

from . import models
from .main import describe, create
from .client import PRAXClient

from .utils import echoerr

@describe.command(name='user', help='List PRAX Users')
@click.option('--org', help='Organization name to show resources for', default=None, type=str)
@click.pass_context
@login_required
def describe_user(ctx: click.Context, org: str|None):
    client = PRAXClient(ctx)
    fields = [
        RenderField(label='Username', path='$.username'),
        RenderField(label='Email', path='$.email'),
        RenderField(label='PRAX API Token', path='$.token'),
        RenderField(label='Current Org.', path='$.current_org.name'),
        RenderField(label='Member of Orgs.', path='$.all_orgs.*', sep=os.linesep),
        RenderField(label='Deployable Orgs.', path='$.deployable_orgs.*', sep=os.linesep),
        RenderField(label='Admin Orgs.', path='$.admin_orgs.*', sep=os.linesep),
        RenderField(label='Deployed Projects', path='$.projects.*', sep=os.linesep),
        RenderField(
            label=f'User-Resources:',
            path='$.current_org.resources.*',
            sep=os.linesep,
            mod=lambda x: f"{x['resource_type'].removesuffix('s')}: {x['name']} (keys: {','.join(x['spec']['data'].keys())})"
        ),
    ]
    users = client.get_users()
    if isinstance(users, list) and org:
        current_org = client.get_org(org)
        if isinstance(current_org, models.ErrorResponse):
            click.echo(f" {err} Error fetching organization '{org}' details:")
            echoerr(current_org)
            return 1
        for user in users:
            user.current_org = current_org
    if isinstance(users, models.ErrorResponse):
        click.echo(f" {err} Error fetching users:")
        echoerr(users)
        return 1
    else:
        click.echo(Renderer(data=users, fields=fields).render_table(tablefmt='plain'))
        user_org = users[0].current_org
        if user_org is not None:
            quotas = list(user_org.tier.model_fields.keys())
            usage = user_org.usage.model_dump()
            tier = user_org.tier.model_dump()
            quota_data = {quotas[i]: j for i, j in enumerate(
                            zip(usage.values(), tier.values()))}
            mod = lambda x: f"{x[0]} / {x[1]}"
            cpu_fields = [
                RenderField(label='Total CPU (millicores)', path='$.max_cpu', mod=mod),
                RenderField(label='CPU per Service (millicores)', path='$.max_cpu_per_service', mod=mod),
                RenderField(label='CPU per Task (millicores)', path='$.max_cpu_per_task', mod=mod),
                RenderField(label='Total GPU (cores)', path='$.max_gpu', mod=mod),
            ]
            ram_fields = [
                RenderField(label='Total Memory (MB)', path='$.max_memory', mod=mod),
                RenderField(label='Memory per Service (MB)', path='$.max_memory_per_service', mod=mod),
                RenderField(label='Memory per Task (MB)', path='$.max_memory_per_task', mod=mod),
            ]
            ephemeral_storage_fields = [
                RenderField(label='Ephemeral Storage (MB)', path='$.max_ephemeral_storage', mod=mod),
                RenderField(label='Ephemeral Storage per Service (MB)', path='$.max_ephemeral_storage_per_service', mod=mod),
                RenderField(label='Ephemeral Storage per Task (MB)', path='$.max_ephemeral_storage_per_task', mod=mod),
            ]
            persistent_storage_fields = [
                RenderField(label='Total Persistent Storage (MB)', path='$.max_persistent_storage', mod=mod),
                RenderField(label='Persistent Storage Size (MB)', path='$.max_persistent_volume_size', mod=mod),
                RenderField(label='Number of Persistent Volumes', path='$.max_persistent_volumes', mod=mod),
            ]

            project_limits_fields = [
                RenderField(label='Total Projects', path='$.max_projects', mod=mod),
                RenderField(label='Total Stages', path='$.max_stages', mod=mod),
                RenderField(label='Total Builds', path='$.max_builds', mod=mod),
                RenderField(label='Total Private Images', path='$.max_images', mod=mod),
                RenderField(label='Total Sources', path='$.max_sources', mod=mod),
                RenderField(label='Total Pipelines', path='$.max_pipelines', mod=mod),
                RenderField(label='Total Tasks', path='$.max_tasks', mod=mod),
                RenderField(label='Total Notebooks', path='$.max_notebooks', mod=mod),
                RenderField(label='Total Services', path='$.max_services', mod=mod),
                RenderField(label='Total Secrets', path='$.max_secrets', mod=mod),
                RenderField(label='Total Config-maps', path='$.max_configmaps', mod=mod),
                #RenderField(label='Total Concurrent Runs', path='$.max_concurrent_workflows', mod=mod),
            ]
            compute_fields = cpu_fields + ram_fields + ephemeral_storage_fields + persistent_storage_fields

            click.echo()
            click.echo(f"Resource Quotas for Organization: {user_org.name}")
            click.echo(f"Quota Tier: {user_org.tier.name}")
            click.echo()
            click.echo("Compute Resources:             (Usage / Limit)")
            click.echo("---------------------------------------------")
            click.echo(Renderer(data=quota_data, fields=compute_fields).render_table(tablefmt='plain'))
            click.echo()
            click.echo("Project Resource Limits:   (Usage / Limit)")
            click.echo("------------------------------------------")
            click.echo(Renderer(data=quota_data, fields=project_limits_fields).render_table(tablefmt='plain'))
        return 0


@create.command(name='user-secret', help='Create a new PRAX User Secret (API Token)')
@click.pass_context
@click.argument('name', type=str)
@click.option('--org', help='Organization name. Defaults to your current Org.', default=None, type=str)
@click.option('--description', help='Secret description', type=str, default=None)
@click.option('--data','-d', help='Secret data key=value pairs', type=str, multiple=True)
@login_required
def create_user_secret(ctx: click.Context,
                       name: str,
                       org: str|None,
                       description: str|None,
                       data: list[str],
):
    client = PRAXClient(ctx)
    users = client.get_users()
    if isinstance(users, models.ErrorResponse):
        click.echo(f" {err} Error fetching User information:")
        echoerr(users)
        return 1
    elif users:
        user = users[0]
    else:
        click.echo(f" {err} No user information found.")
        return 1

    if not user.current_org:
        click.echo(f" {err} No organization specified and user '{user.username}' has no current Org.")
        return 1
    
    org = org or user.current_org.name
    user_id = getattr(user.email, 'root', user.username)
    
    if org not in user.admin_orgs:
        click.echo(f" {err} Failed to create or update User-Secret!")
        click.echo(f" {wrn} User '{user_id}' cannot manage User Resources from Organization '{org}'")
        return 1

    try:
        secret_data = {s[0]: s[1] for s in [d.split('=') for d in data]}
    except ValueError:
        click.echo(f" {err} Failed to create or update User-Secret!")
        click.echo(f" {wrn} Error parsing secret data. Please provide key=value pairs.")
        return 1

    secret = client.create_or_update_user_secret(name, org, secret_data, description)

    if isinstance(secret, models.ErrorResponse):
        click.echo(f" {err} Failed to create or update User-Secret!")
        echoerr(secret)
        return 1
    else:
        click.echo(f" {chk} User-Secret '{secret.name}' created successfully in '{org}' namespace!")
