
import click

from oceanum.cli.common.renderer import Renderer, RenderField
from oceanum.cli.common.symbols import err, chk
from oceanum.cli.auth import login_required

from . import models
from .main import describe, create
from .client import PRAXClient

from .utils import echoerr

@describe.command(name='user', help='List PRAX Users')
@click.pass_context
@login_required
def describe_user(ctx: click.Context):
    client = PRAXClient(ctx)
    fields = [
        RenderField(label='Username', path='$.username'),
        RenderField(label='Email', path='$.email'),
        RenderField(label='PRAX API Token', path='$.token'),
        RenderField(label='Current Org.', path='$.current_org'),
        RenderField(label='Deployable Orgs.', path='$.deployable_orgs.*', sep='\n'),
        RenderField(label='Admin Orgs.', path='$.admin_orgs.*', sep='\n'),
        RenderField(
            label='Org Tiers', 
            path='$.orgs.*', 
            sep='\n',
            mod=lambda x: f"{x['name']}: {x['tier']['name']}"
        ),
        RenderField(label='Deployed Projects', path='$.projects.*', sep='\n'),
        RenderField(
            label='User Resources', 
            path='$.orgs.*.resources.*', 
            sep='\n',
            mod=lambda x: f"{x['org']}/{x['resource_type'].removesuffix('s')}: {x['name']}"
        ),
    ]
    users = client.get_users()
    if isinstance(users, models.ErrorResponse):
        click.echo(f" {err} Error fetching users:")
        echoerr(users)
        return 1
    else:
        click.echo(Renderer(data=users, fields=fields).render_table(tablefmt='plain'))

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
        click.echo(f" {err} Error fetching users:")
        echoerr(users)
        return 1
    else:
        user = users[0]
    current_org = org or user.current_org
    
    if not current_org:
        click.echo(f" {err} No organization specified and user '{user.username}' has no current Org.")
        return 1
    elif current_org not in user.admin_orgs:
        click.echo(f" {err} User '{user.username}' is not an admin of Org. '{current_org}'")
        return 1
    
    user_org_secrets = []

    org_spec = [o for o in user.orgs if o.name == current_org]
    
    if not org_spec:
        click.echo(f" {err} User '{user.username}' is not deployable to Org. '{current_org}'")
        return 1
    else:
        org_spec = org_spec[0]

        
    for r in org_spec.resources:
        if r.resource_type == 'secret' and r.org == current_org:
            user_org_secrets.append(r.name)

    if name in user_org_secrets:
        view = click.confirm(f"User secret '{name}' on Org. '{current_org}' already exists, do you want to update it?")
        if not view:
            click.echo("User secret creation aborted!")
            return 0
        
    try:
        secret_data = {s[0]: s[1] for s in [d.split('=') for d in data]}
    except ValueError:
        click.echo(f" {err} Error parsing secret data. Please provide key=value pairs.")
        return 1

    secret = client.create_or_update_user_secret(name, current_org, secret_data, description)

    if isinstance(secret, models.ErrorResponse):
        click.echo(f" {err} Error creating user secret:")
        echoerr(secret)
        return 1
    else:
        click.echo(f" {chk} User-secret created successfully at Org. '{current_org}': {secret.name}")