
import click

from oceanum.cli.common.renderer import Renderer, RenderField
from oceanum.cli.common.symbols import err
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
        RenderField(label='Organizations', path='$.orgs.*', sep='\n'),
        RenderField(
            label='User Resources', 
            path='$.resources.*', 
            sep='\n',
            mod=lambda x: f"{x['resource_type'].removesuffix('s')}: {x['name']}"),
    ]
    users = client.get_users()
    if isinstance(users, models.ErrorResponse):
        click.echo(f"{err} Error fetching users:")
        echoerr(users)
        return 1
    else:
        click.echo(Renderer(data=users, fields=fields).render_table(tablefmt='plain'))

@create.command(name='user-secret', help='Create a new PRAX User Secret (API Token)')
@click.pass_context
@click.argument('name', type=str)
@click.option('--org', help='Organization name', default=None, type=str)
@click.option('--data','-d', help='Secret data', type=str, multiple=True)
@login_required
def create_user_secret(ctx: click.Context, name: str, org: str|None, data: list[str]):
    client = PRAXClient(ctx)
    users = client.get_users()
    if isinstance(users, models.ErrorResponse):
        click.echo(f"{err} Error fetching users:")
        echoerr(users)
        return 1
    else:
        user = users[0]
    current_org = org or user.current_org
    user_org_secrets = []
    for r in user.resources:
        if r.resource_type == 'secret' and r.org == current_org:
            user_org_secrets.append(r.name)

    if name in user_org_secrets:
        view = click.confirm(f"User secret '{name}' on Org. '{current_org}' already exists, do you want to update it?")
        if not view:
            click.echo("User secret creation aborted!")
            return 0
    
    secret_data = {s[0]: s[1] for s in [d.split('=') for d in data]}

    secret = client.create_or_update_user_secret(name, org, )

    if isinstance(secret, models.ErrorResponse):
        click.echo(f"{err} Error creating user secret:")
        echoerr(secret)
        return 1
    else:
        click.echo(f"User secret created: {secret['token']}")