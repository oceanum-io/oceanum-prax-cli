
import click

from oceanum.cli.common.renderer import Renderer, RenderField
from oceanum.cli.common.symbols import err
from oceanum.cli.auth import login_required

from . import models
from .main import describe
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
        RenderField(label='Current Org', path='$.current_org.name'),
        RenderField(label='PRAX API Token', path='$.token'),
        RenderField(
            label='User Resources', 
            path='$.resources.*', 
            mod=lambda x: f"{x['resource_type'].removesuffix('s')}: {x['name']}"),
    ]
    users = client.get_users()
    if isinstance(users, models.ErrorResponse):
        click.echo(f"{err} Error fetching users:")
        echoerr(users)
        return 1
    else:
        click.echo(Renderer(data=users, fields=fields).render(output_format='plain'))