import sys
import yaml
from os import linesep

import click

from oceanum.cli.common.renderer import Renderer, output_format_option, RenderField
from oceanum.cli.auth import login_required
from oceanum.cli.common.symbols import wrn, chk, info, err
from . import models
from .main import list_group, describe, submit
from .client import PRAXClient

from .utils import format_route_status as _frs, echoerr


@list_group.command(name='pipelines', help='List PRAX Pipelines')
@click.pass_context
@click.option('--search', help='Search by names or description', 
              default=None, type=str)
@click.option('--org', help='Organization name', default=None, type=str)
@click.option('--user', help='Project owner email', default=None, type=str)
@click.option('--project', help='Project name', default=None, type=str)
@click.option('--stage', help='Stage name', default=None, type=str)
@output_format_option
@login_required
def list_pipelines(ctx: click.Context, output: str, **filters):
    client = PRAXClient(ctx)
    fields = [
        RenderField(label='Name', path='$.name'),
        RenderField(label='Project', path='$.project'),
        RenderField(label='Stage', path='$.stage'),
        RenderField(label='Org.', path='$.org'),
        RenderField(label='Object', path='$.object_ref'),
        RenderField(label='Last Run', path='$.last_run', mod=lambda x: x['status'] if x is not None else 'N/A'),
        RenderField(label='Started at', path='$.last_run', mod=lambda x: x['started_at'] if x is not None else 'N/A'),
    ]
    pipelines =  client.list_pipelines(**{
        k: v for k, v in filters.items() if v is not None
    })
    if not pipelines:
        click.echo('No pipelines found!')
    elif isinstance(pipelines, models.ErrorResponse):
        click.echo(f"{wrn} Error fetching pipelines:")
        echoerr(pipelines)
        sys.exit(1)
    else:
        click.echo(Renderer(data=pipelines, fields=fields).render(output_format=output))

@describe.command(name='pipeline', help='Describe PRAX Pipeline')
@click.pass_context
@click.argument('name', type=str)
@click.option('--org', help='Organization name', default=None, type=str)
@click.option('--user', help='Project owner email', default=None, type=str)
@click.option('--project', help='Project name', default=None, type=str)
@click.option('--stage', help='Stage name', default=None, type=str)
@login_required
def describe_pipeline(ctx: click.Context, name: str, **filters):
    client = PRAXClient(ctx)
    pipeline = client.get_pipeline(name)
    if isinstance(pipeline, models.ErrorResponse):
        click.echo(f"{wrn} Error fetching pipeline:")
        echoerr(pipeline)
        sys.exit(1)
    else:
        click.echo(Renderer(data=[pipeline], fields=[]).render(output_format='yaml'))


@submit.command(name='pipeline', help='Submit PRAX Pipeline')
@click.pass_context
@click.argument('name', type=str)
@click.option('--org', help='Organization name', default=None, type=str)
@click.option('--user', help='Project owner email', default=None, type=str)
@click.option('--project', help='Project name', default=None, type=str)
@click.option('--stage', help='Stage name', default=None, type=str)
@click.option('-p','--parameter', help='Pipeline parameters', default=None, type=str, multiple=True)
@login_required
def submit_pipeline(ctx: click.Context, name: str, ):
    client = PRAXClient(ctx)
    pipeline = client.get_pipeline(name)
    if isinstance(pipeline, models.ErrorResponse):
        click.echo(f"{wrn} Error fetching pipeline:")
        echoerr(pipeline)
        sys.exit(1)
    else:
        click.echo(Renderer(data=[pipeline], fields=[]).render(output_format='yaml'))
        click.echo(f"{info} Pipeline submitted successfully!")