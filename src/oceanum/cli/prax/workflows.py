import sys

import click

from oceanum.cli.common.renderer import Renderer, output_format_option, RenderField
from oceanum.cli.auth import login_required
from oceanum.cli.common.symbols import wrn, chk, info, err, spin
from oceanum.cli.common.utils import format_dt

from . import models
from .main import list_group, describe, submit
from .client import PRAXClient
from .project import (
    project_org_option, 
    project_user_option, 
    project_stage_option, 
    project_name_option,
    name_arguement
)
from .utils import format_route_status as _frs, echoerr

LIST_FIELDS = [
    RenderField(label='Name', path='$.name'),
    RenderField(label='Project', path='$.project'),
    RenderField(label='Stage', path='$.stage'),
    RenderField(label='Org.', path='$.org'),
    RenderField(
        label='Last Run', 
        path='$.last_run', 
        mod=lambda x: x['status'] if x is not None else 'N/A'
    ),
    RenderField(
        label='Started at', 
        path='$.last_run', 
        mod=lambda x: x['started_at'] if x is not None else 'N/A'
    ),
]

@list_group.command(name='pipelines', help='List PRAX Pipelines')
@click.pass_context
@click.option('--search', help='Search by names or description', 
              default=None, type=str)
@project_org_option
@project_user_option
@project_name_option
@project_stage_option
@output_format_option
@login_required
def list_pipelines(ctx: click.Context, output: str, **filters):
    client = PRAXClient(ctx)
    pipelines =  client.list_pipelines(**{
        k: v for k, v in filters.items() if v is not None
    })
    def format_schedule(x: list) -> list[str]:
        if len(x) == 2 and x[1] is not None:
            icon = spin if not x[0] else err
            return [f"{icon} {x[1]}"]
        else:
            return ['N/A']
        
    extra_fields = [
        RenderField(
            label='Schedule', 
            path='$.["suspended", "schedule"]',
            lmod=format_schedule,
            sep=' '
        ),
    ]
    if not pipelines:
        click.echo('No pipelines found!')
    elif isinstance(pipelines, models.ErrorResponse):
        click.echo(f"{wrn} Error fetching pipelines:")
        echoerr(pipelines)
        sys.exit(1)
    else:
        click.echo(Renderer(
            data=pipelines, 
            fields=LIST_FIELDS+extra_fields
        ).render(output_format=output))

@list_group.command(name='tasks', help='List all PRAX Tasks')
@click.pass_context
@click.option('--search', help='Search by names or description', 
              default=None, type=str)
@project_org_option
@project_user_option
@project_name_option
@project_stage_option
@output_format_option
@login_required
def list_tasks(ctx: click.Context, output: str, **filters):
    client = PRAXClient(ctx)
    tasks =  client.list_tasks(**{
        k: v for k, v in filters.items() if v is not None
    })
    if not tasks:
        click.echo('No tasks found!')
    elif isinstance(tasks, models.ErrorResponse):
        click.echo(f"{wrn} Error fetching tasks:")
        echoerr(tasks)
        sys.exit(1)
    else:
        click.echo(Renderer(data=tasks, fields=LIST_FIELDS).render(output_format=output))

@list_group.command(name='builds', help='List all PRAX Builds')
@click.pass_context
@click.option('--search', help='Search by names or description',
                default=None, type=str)
@project_org_option
@project_user_option
@project_name_option
@project_stage_option
@output_format_option
@login_required
def list_builds(ctx: click.Context, output: str, **filters):
    client = PRAXClient(ctx)
    builds =  client.list_builds(**{
        k: v for k, v in filters.items() if v is not None
    })
    if not builds:
        click.echo('No builds found!')
    elif isinstance(builds, models.ErrorResponse):
        click.echo(f"{wrn} Error fetching builds:")
        echoerr(builds)
        sys.exit(1)
    else:
        click.echo(Renderer(data=builds, fields=LIST_FIELDS).render(output_format=output))


@describe.command(name='pipeline', help='Describe PRAX Pipeline')
@click.pass_context
@name_arguement
@project_org_option
@project_user_option
@project_name_option
@project_stage_option
@login_required
def describe_pipeline(ctx: click.Context, name: str, **filters):
    client = PRAXClient(ctx)
    pipeline = client.get_pipeline(name)
    pipeline_fields = [
        RenderField(label='Pipeline Name', path='$.name'),
        RenderField(label='Description', path='$.description'),
        RenderField(label='Project', path='$.project'),
        RenderField(label='Organization', path='$.org'),
        RenderField(label='Stage', path='$.stage'),
        RenderField(label='Object Ref.', path='$.object_ref'),
        RenderField(label='Schedule', path='$.schedule'),
        RenderField(label='Suspended', path='$.suspended', ),
        RenderField(label='Created At', path='$.created_at', mod=format_dt),
        RenderField(label='Updated At', path='$.updated_at', mod=format_dt),
    ]
    run_fields = [
        RenderField(label='Object Ref', path='$.object_ref'),
        RenderField(label='Status', path='$.status'),
        RenderField(label='Started at', path='$.started_at', mod=format_dt),
        RenderField(label='Finished at', path='$.finished_at', mod=lambda x: format_dt(x) if x is not None else 'N/A'),
        RenderField(label='Message', path='$.message'),
    ]
    if isinstance(pipeline, models.PipelineSchema):
        click.echo(Renderer(
            data=[pipeline], 
            fields=pipeline_fields
        ).render(output_format='table', tablefmt='plain'))
        # if pipeline.details:
        #     click.echo(f"  {chk} Pipeline Details:")
        #     click.echo(Renderer(
        #         data=[pipeline.details],
        #         fields=[], indent=2
        #     ).render(output_format='yaml'))
        if pipeline.last_run:
            click.echo(f"Last Run:")
            click.echo(Renderer(
                data=[pipeline.last_run], 
                fields=run_fields, 
                indent=2
            ).render(output_format='table', tablefmt='plain'))
            if pipeline.last_run.arguments:
                click.echo(f"    Arguments:")
                click.echo(Renderer(
                    data=[pipeline.last_run.arguments], 
                    fields=[], 
                    indent=4
                ).render(output_format='yaml'))
            if pipeline.last_run.details:
                click.echo(f"  Run Details:")
                click.echo(Renderer(
                    data=[pipeline.last_run.details], 
                    fields=[], 
                    indent=2
                ).render(output_format='yaml'))

    else:
        click.echo(f"{wrn} Error fetching pipeline:")
        echoerr(pipeline)
        sys.exit(1)


@submit.command(name='pipeline', help='Submit PRAX Pipeline')
@click.pass_context
@name_arguement
@project_org_option
@project_user_option
@project_name_option
@project_stage_option
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

