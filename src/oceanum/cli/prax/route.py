import sys
import yaml
from os import linesep

import click

from oceanum.cli.common.renderer import Renderer, output_format_option, RenderField
from oceanum.cli.auth import login_required
from oceanum.cli.common.symbols import wrn, chk, info, err
from . import models
from .main import list_group, describe, update, allow, logs
from .client import PRAXClient

from .utils import format_route_status as _frs, echoerr

@update.group(name='route', help='Update PRAX Routes')
def update_route():
    pass

@list_group.command(name='routes', help='List PRAX Routes')
@click.pass_context
@click.option('--search', help='Search by route name, project_name or project description', 
              default=None, type=str)
@click.option('--org', help='Organization name', default=None, type=str)
@click.option('--user', help='Route owner email', default=None, type=str)
@click.option('--status', help='Route status', default=None, type=str)
@click.option('--project', help='Project name', default=None, type=str)
@click.option('--stage', help='Stage name', default=None, type=str)
@click.option('--open-access', help='Show only open-access routes or private routes with False', default=None, type=bool, is_flag=True)
@click.option('--tier', help="Select only 'frontend' or 'backend' routes", default=None, type=click.Choice(['backend','frontend']))
@click.option('--current-org', help='Filter routes by the current organization in Oceanum.io', default=False, type=bool, is_flag=True)
@output_format_option
@login_required
def list_routes(ctx: click.Context, output: str, open_access: bool, current_org: bool, **filters):
    if open_access:
        filters.update({'open': True})
    elif open_access is None:
        pass
    else:
        filters.update({'open': False})

    if current_org:
        filters.update({'active_org': True})

    client = PRAXClient(ctx)
    fields = [
        RenderField(label='Route Name', path='$.name'),
        RenderField(label='Project', path='$.project'),
        RenderField(label='Stage', path='$.stage'),
        RenderField(label='Status', path='$.status', mod=_frs),
        RenderField(label='URL', path='$.url'),
    ]
    routes =  client.list_routes(**{
        k: v for k, v in filters.items() if v is not None
    })
    if not routes:
        click.echo(f' {wrn} No routes found!')
    elif isinstance(routes, models.ErrorResponse):
        click.echo(f" {err} Error fetching routes:")
        echoerr(routes)
        sys.exit(1)
    else:
        click.echo(Renderer(data=routes, fields=fields).render(output_format=output))

@list_group.command(name='notebooks', help='List PRAX Notebooks')
@click.pass_context
@click.option('--search', help='Search by notebook name, project_name or project description',
              default=None, type=str)
@click.option('--org', help='Organization name', default=None, type=str)
@click.option('--user', help='Notebook owner email', default=None, type=str)
@click.option('--status', help='Notebook status', default=None, type=str)
@click.option('--project', help='Project name', default=None, type=str)
@click.option('--stage', help='Stage name', default=None, type=str)
@click.option('--open-access', help='Show only open-access notebooks or private notebooks with False', default=None, type=bool, is_flag=True)
@output_format_option
@login_required
def list_notebooks(ctx: click.Context, output: str, open_access: bool, **filters):
    filters.update({'notebook': True})
    ctx.invoke(list_routes, output=output, open_access=open_access, **filters)

@describe.command(name='route', help='Describe a PRAX Service or App Route')
@click.pass_context
@click.argument('route_name', type=str)
@login_required
def describe_route(ctx: click.Context, route_name: str):
    client = PRAXClient(ctx)
    route = client.get_route(route_name)
    if isinstance(route, models.RouteSchema):
        fields = [
            RenderField(label='Name', path='$.name'),
            RenderField(label='Description', path='$.description'),
            RenderField(label='Project', path='$.project'),
            RenderField(label='Service', path='$.service_name'),
            RenderField(label='Stage', path='$.stage'),
            RenderField(label='Org', path='$.org'),
            RenderField(label='Default URL', path='$.url'),
            RenderField(label='Created At', path='$.created_at'),
            RenderField(label='Updated At', path='$.updated_at'),
            RenderField(label='Current Revision', path='$.revision'),
            RenderField(label='Next Revision', path='$.next_revision'),
            RenderField(label='Next Revision Status', path='$.next_revision_status'),
            RenderField(
                label='Custom Domains', 
                path='$.custom_domains.*', 
                sep=linesep, 
                mod=lambda x: f'https://{x}' if x else None
            ),
            RenderField(label='Publish App', path='$.publish_app'),
            RenderField(label='Open Access', path='$.open_access'),
            RenderField(label='Thumbnail URL', path='$.thumbnail'),
            RenderField(label='Status', path='$.status'),
            RenderField(label='Details', path='$.details', 
                        mod=lambda x: yaml.dump(x, indent=4) if x else None
            ),
        ]
            
        click.echo(
            Renderer(data=[route], fields=fields).render(output_format='table', tablefmt='plain')
        )
    else:
        click.echo(f" {err} Error fetching route:")
        echoerr(route)
        sys.exit(1)

@update_route.command(name='thumbnail', help='Update a PRAX Route thumbnail')
@click.pass_context
@click.argument('route_name', type=str)
@click.argument('thumbnail_file', type=click.File('rb'))
@login_required
def update_thumbnail(ctx: click.Context, route_name: str, thumbnail_file: click.File):
    client = PRAXClient(ctx)
    route = client.get_route(route_name)
    if route is not None:
        click.echo(f"Updating thumbnail for route '{route_name}'...")
        thumbnail = client.update_route_thumbnail(route_name, thumbnail_file)
        if isinstance(thumbnail, models.ErrorResponse):
            click.echo(f"{wrn} Error updating thumbnail:")
            echoerr(thumbnail)
        else:
            click.echo(f"Thumbnail updated successfully for route '{route_name}'!")
    else:
        click.echo(f"Route '{route_name}' not found!")
        

@allow.command(name='route')
@click.argument('route_name', type=str, required=True)
@click.option('-g','--group', type=str, required=False, multiple=True)
@click.option('-u','--user', type=str, required=False, multiple=True)
@click.option('-v','--view', help='Allow to view the route', default=None, type=bool, is_flag=True)
@click.option('-c','--change', help='Allow to change the route, implies --view', default=None, type=bool, is_flag=True)
@click.option('-a','--assign', help='Allow to assign route permissions', default=None, type=bool, is_flag=True)
@click.pass_context
@login_required
def allow_route(ctx: click.Context, route_name: str, group: list[str], 
                user: list[str], view: bool, change: bool, assign: bool):
    
    def _get_perm(subject: str):
        return models.PermissionsSchema(
            subject=subject,
            view=view if view is not None else None,
            change=change if change is not None else None,
            assign=assign if assign is not None else None
        )

    client = PRAXClient(ctx)
    response = client.get_route(route_name)

    if isinstance(response, models.RouteSchema):
        permissions = models.ResourcePermissionsSchema(
            groups=[_get_perm(g) for g in group],
            users=[_get_perm(u) for u in user],
        )
        response = client.allow_route(response.name, permissions)
        if not isinstance(response, models.ErrorResponse):
            click.echo(f"{chk} Permissions for route '{route_name}' updated successfully!")
            click.echo(f"{info} {response}")
    if isinstance(response, models.ErrorResponse):
        click.echo(f" {err} Failed to grant permission to route!")
        echoerr(response)
        sys.exit(1)

@logs.command(name='route', help='Get logs for a PRAX Route')
@click.pass_context
@click.argument('route_name', type=str)
@click.option('-n','--lines', help='Number of lines to show', default=1000, type=int)
@click.option('-f','--follow', help='Follow logs', default=False, type=bool, is_flag=True)
@login_required
def get_route_logs(ctx: click.Context, route_name: str, lines: int, follow: bool):
    client = PRAXClient(ctx)
    for line in client.get_route_logs(route_name, lines, follow):
        if isinstance(line, models.ErrorResponse):
            click.echo(f" {err} Error fetching logs:")
            echoerr(line)
            sys.exit(1)
        click.echo(line)