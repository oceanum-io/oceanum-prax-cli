import sys
import time
import click

from oceanum.cli.common.renderer import Renderer, output_format_option, RenderField
from oceanum.cli.auth import login_required
from oceanum.cli.common.symbols import chk, err, spin, wrn
from oceanum.cli.common.utils import format_dt

from . import models
from .main import list_group, describe, submit, terminate, retry, logs
from .client import PRAXClient
from .project import (
    project_org_option, 
    project_user_option, 
    project_stage_option, 
    project_name_option,
    name_argument
)
from .utils import echoerr, format_run_status as frs

def parse_parameters(parameters: list[str]|None) -> dict|None:
    params = {}
    if parameters is not None:
        for p in parameters:
            key, value = p.split('=')
            params[key] = value
    return params or None


LIST_FIELDS = [
    RenderField(label='Name', path='$.name'),
    RenderField(label='Project', path='$.project'),
    RenderField(label='Stage', path='$.stage'),
    RenderField(label='Org.', path='$.org'),
    RenderField(
        label='Last Run', 
        path='$.last_run', 
        mod=lambda x: frs(x['status']) if x is not None else 'N/A'
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
    pipelines =  client.list_pipelines(**filters)
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
        click.echo(f' {wrn} No pipelines found!')
    elif isinstance(pipelines, models.ErrorResponse):
        click.echo(f" {err} Error fetching pipelines:")
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
    tasks =  client.list_tasks(**filters)
    if not tasks:
        click.echo(f' {wrn} No tasks found!')
    elif isinstance(tasks, models.ErrorResponse):
        click.echo(f" {err} Error fetching tasks:")
        echoerr(tasks)
        sys.exit(1)
    else:
        click.echo(Renderer(data=tasks, fields=LIST_FIELDS).render(output_format=output))

@describe.command(name='task', help='Describe PRAX Task')
@click.pass_context
@name_argument
@project_org_option
@project_user_option
@project_name_option
@project_stage_option
@login_required
def describe_task(ctx: click.Context, name: str, **filters):
    client = PRAXClient(ctx)
    task = client.get_task(name, **filters)
    task_fields = [
        RenderField(label='Task Name', path='$.name'),
        RenderField(label='Description', path='$.description'),
        RenderField(label='Project', path='$.project'),
        RenderField(label='Organization', path='$.org'),
        RenderField(label='Stage', path='$.stage'),
        RenderField(label='Created At', path='$.created_at', mod=format_dt),
        RenderField(label='Updated At', path='$.updated_at', mod=format_dt),
    ]
    run_fields = [
        RenderField(label='Status', path='$.status'),
        RenderField(label='Started at', path='$.started_at', mod=format_dt),
        RenderField(label='Finished at', path='$.finished_at', mod=lambda x: format_dt(x) if x is not None else 'N/A'),
        RenderField(label='Message', path='$.message'),
    ]
    if isinstance(task, models.TaskSchema):
        click.echo(Renderer(
            data=[task], 
            fields=task_fields
        ).render(output_format='table', tablefmt='plain'))
        if task.last_run:
            click.echo("Last Run:")
            click.echo(Renderer(
                data=[task.last_run], 
                fields=run_fields, 
                indent=2
            ).render(output_format='table', tablefmt='plain'))
            if task.last_run.arguments:
                click.echo("    Arguments:")
                click.echo(Renderer(
                    data=[task.last_run.arguments], 
                    fields=[], 
                    indent=4
                ).render(output_format='yaml'))
            if task.last_run.details:
                click.echo("  Run Details:")
                click.echo(Renderer(
                    data=[task.last_run.details], 
                    fields=[], 
                    indent=2
                ).render(output_format='yaml'))
    else:
        click.echo(f" {err} Error fetching task:")
        echoerr(task)
        sys.exit(1)

@submit.command(name='task', help='Submit PRAX Task')
@click.pass_context
@name_argument
@project_org_option
@project_user_option
@project_name_option
@project_stage_option
@click.option('-p','--parameter', help='Task parameters', default=None, type=str, multiple=True)
@login_required
def submit_task(ctx: click.Context, name: str, parameter: list[str]|None, **filters):
    client = PRAXClient(ctx)
    task = client.get_task(name, **filters)
    
    if isinstance(task, models.ErrorResponse):
        click.echo(f" {err} Error fetching task:")
        echoerr(task)
        sys.exit(1)
    else:
        resp = client.submit_task(name, parse_parameters(parameter), **filters)
        if isinstance(resp, models.ErrorResponse):
            click.echo(f" {err} Error submitting task:")
            echoerr(resp)
            sys.exit(1)
        else:
            click.echo(f"{chk} Task submitted successfully! Run ID: {'N/A' if resp.last_run is None else resp.last_run.name}")


@terminate.command(name='task', help='Terminate PRAX Task')
@click.pass_context
@name_argument
@project_org_option
@project_user_option
@project_name_option
@project_stage_option
@login_required
def terminate_task(ctx: click.Context, name: str, **filters):
    client = PRAXClient(ctx)
    task = client.get_task_run(name)
    
    if isinstance(task, models.ErrorResponse):
        click.echo(f" {err} Error fetching task:")
        echoerr(task)
        sys.exit(1)
    else:
        click.echo(f" {spin} Terminating task: {name} ...")
        resp = client.terminate_task_run(name, **filters)
        if isinstance(resp, models.ErrorResponse):
            click.echo(f" {err} Error terminating task:")
            echoerr(resp)
            sys.exit(1)
        else:
            while True:
                task = client.get_task_run(name)
                if isinstance(task, models.ErrorResponse):
                    click.echo(f" {err} Error fetching task:")
                    echoerr(task)
                    sys.exit(1)
                elif task and task.status == 'Running':
                    time.sleep(1)
                    continue
                else:
                    break
            click.echo(f"{chk} Task {task.name} terminated successfully!")

@retry.command(name='task', help='Retry PRAX Task')
@click.pass_context
@name_argument
@project_org_option
@project_user_option
@project_name_option
@project_stage_option
@login_required
def retry_task(ctx: click.Context, name: str, **filters):
    client = PRAXClient(ctx)
    task = client.get_task_run(name)
    if isinstance(task, models.ErrorResponse):
        click.echo(f" {err} Error fetching task:")
        echoerr(task)
        sys.exit(1)
    else:
        resp = client.retry_task_run(name, **filters)
        if isinstance(resp, models.ErrorResponse):
            click.echo(f" {err} Error retrying task:")
            echoerr(resp)
            sys.exit(1)
        else:
            click.echo(f"{chk} Task retried successfully! Run ID: {'N/A' if resp is None else resp.name}")


@logs.command(name='task', help='Get the Latest Run PRAX Task logs')
@click.pass_context
@name_argument
@project_org_option
@project_user_option
@project_name_option
@project_stage_option
@click.option('-n','--lines', help='Number of lines to show', default=1000, type=int)
@click.option('-f','--follow', help='Follow logs', default=False, type=bool, is_flag=True)
@login_required
def get_task_logs(ctx: click.Context, name: str, lines: int, follow: bool, **filters):
    client = PRAXClient(ctx)
    task = client.get_task(name, **filters)
    if isinstance(task, models.ErrorResponse):
        click.echo(f" {err} Error fetching task:")
        echoerr(task)
        sys.exit(1)
    if task.last_run is None:
        click.echo(f" {err} No active runs found for task '{name}'!")
        sys.exit(1)

    latest_run = task.last_run
    click.echo(f"Fetching logs for task run: {latest_run.name} ...")
    for line in client.get_task_run_logs(latest_run.name, lines, follow):
        if isinstance(line, models.ErrorResponse):
            click.echo(f" {err} Error fetching logs:")
            echoerr(line)
            sys.exit(1)
        click.echo(line)


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
    build_fields = LIST_FIELDS + [
        RenderField(label='Source Branch/Tag', path='$.source_ref'),
    ]
    #build_fields.pop(-2)
    client = PRAXClient(ctx)
    builds =  client.list_builds(**{
        k: v for k, v in filters.items() if v is not None
    })
    if not builds:
        click.echo(f' {wrn} No builds found!')
    elif isinstance(builds, models.ErrorResponse):
        click.echo(f" {err} Error fetching builds:")
        echoerr(builds)
        sys.exit(1)
    else:
        click.echo(Renderer(data=builds, fields=build_fields).render(output_format=output))


@describe.command(name='build', help='Describe PRAX Build')
@click.pass_context
@name_argument
@project_org_option
@project_user_option
@project_name_option
@project_stage_option
@login_required
def describe_build(ctx: click.Context, name: str, **filters):
    client = PRAXClient(ctx)
    build = client.get_build(name, **filters)
    build_fields = [
        RenderField(label='Build Name', path='$.name'),
        RenderField(label='Description', path='$.description'),
        RenderField(label='Project', path='$.project'),
        RenderField(label='Organization', path='$.org'),
        RenderField(label='Stage', path='$.stage'),
        RenderField(label='Source Branch/Tag', path='$.source_ref'),
        RenderField(label='Source Commit SHA', path='$.commit_sha'),
        RenderField(label='Created At', path='$.created_at', mod=format_dt),
        RenderField(label='Updated At', path='$.updated_at', mod=format_dt),
    ]
    run_fields = [
        RenderField(label='Status', path='$.status'),
        RenderField(label='Started at', path='$.started_at', mod=format_dt),
        RenderField(label='Finished at', path='$.finished_at', mod=lambda x: format_dt(x) if x is not None else 'N/A'),
        RenderField(label='Message', path='$.message'),
    ]
    if isinstance(build, models.BuildSchema):
        click.echo(Renderer(
            data=[build], 
            fields=build_fields
        ).render(output_format='table', tablefmt='plain'))
        if build.last_run:
            click.echo("Last Run:")
            click.echo(Renderer(
                data=[build.last_run], 
                fields=run_fields, 
                indent=2
            ).render(output_format='table', tablefmt='plain'))
            if build.last_run.arguments:
                click.echo("    Arguments:")
                click.echo(Renderer(
                    data=[build.last_run.arguments], 
                    fields=[], 
                    indent=4
                ).render(output_format='yaml'))
            if build.last_run.details:
                click.echo("  Run Details:")
                click.echo(Renderer(
                    data=[build.last_run.details], 
                    fields=[], 
                    indent=2
                ).render(output_format='yaml'))
    else:
        click.echo(f" {err} Error fetching build:")
        echoerr(build)
        sys.exit(1)

@submit.command(name='build', help='Submit PRAX Build')
@click.pass_context
@name_argument
@project_org_option
@project_user_option
@project_name_option
@project_stage_option
@click.option('-p','--parameter', help='Build parameters', default=None, type=str, multiple=True)
@login_required
def submit_build(ctx: click.Context, name: str, parameter: list[str]|None, **filters):
    client = PRAXClient(ctx)
    build = client.get_build(name, **filters)
    if isinstance(build, models.ErrorResponse):
        click.echo(f" {err} Error fetching build:")
        echoerr(build)
        sys.exit(1)
    else:
        resp = client.submit_build(name, parse_parameters(parameter), **filters)
        if isinstance(resp, models.ErrorResponse):
            click.echo(f" {err} Error submitting build:")
            echoerr(resp)
            sys.exit(1)
        else:
            click.echo(f"{chk} Build submitted successfully! Run ID: {'N/A' if resp.last_run is None else resp.last_run.name}")

@terminate.command(name='build', help='Terminate PRAX Build')
@click.pass_context
@name_argument
@project_org_option
@project_user_option
@project_name_option
@project_stage_option
@login_required
def terminate_build(ctx: click.Context, name: str, **filters):
    client = PRAXClient(ctx)
    build = client.get_build_run(name)
    if isinstance(build, models.ErrorResponse):
        click.echo(f" {err} Error fetching build:")
        echoerr(build)
        sys.exit(1)
    else:
        resp = client.terminate_build_run(name, **filters)
        if isinstance(resp, models.ErrorResponse):
            click.echo(f" {err} Error terminating build:")
            echoerr(resp)
            sys.exit(1)
        else:
            click.echo(f"{chk} Build terminated successfully! Run ID: {'N/A' if resp is None else resp.name}")

@retry.command(name='build', help='Retry PRAX Build')
@click.pass_context
@name_argument
@project_org_option
@project_user_option
@project_name_option
@project_stage_option
@login_required
def retry_build(ctx: click.Context, name: str, **filters):
    client = PRAXClient(ctx)
    build = client.get_build_run(name)
    if isinstance(build, models.ErrorResponse):
        click.echo(f" {err} Error fetching build:")
        echoerr(build)
        sys.exit(1)
    else:
        resp = client.retry_build_run(name, **filters)
        if isinstance(resp, models.ErrorResponse):
            click.echo(f" {err} Error retrying build:")
            echoerr(resp)
            sys.exit(1)
        else:
            click.echo(f"{chk} Build retried successfully! Run ID: {'N/A' if resp is None else resp.name}")


@logs.command(name='build', help='Get the Latest Run PRAX Build logs')
@click.pass_context
@name_argument
@project_org_option
@project_user_option
@project_name_option
@project_stage_option
@click.option('-n','--lines', help='Number of lines to show', default=1000, type=int)
@click.option('-f','--follow', help='Follow logs', default=False, type=bool, is_flag=True)
@login_required
def get_build_logs(ctx: click.Context, name: str, lines: int, follow: bool, **filters):
    client = PRAXClient(ctx)
    build = client.get_build(name, **filters)
    if isinstance(build, models.ErrorResponse):
        click.echo(f" {err} Error fetching build:")
        echoerr(build)
        sys.exit(1)
    if build.last_run is None:
        click.echo(f" {err} No active runs found for build '{name}'!")
        sys.exit(1)

    latest_run = build.last_run
    click.echo(f"Fetching logs for build run: {latest_run.name} ...")
    for line in client.get_build_run_logs(latest_run.name, lines, follow):
        if isinstance(line, models.ErrorResponse):
            click.echo(f" {err} Error fetching logs:")
            echoerr(line)
            sys.exit(1)
        click.echo(line)


@describe.command(name='pipeline', help='Describe PRAX Pipeline')
@click.pass_context
@name_argument
@project_org_option
@project_user_option
@project_name_option
@project_stage_option
@login_required
def describe_pipeline(ctx: click.Context, name: str, **filters):
    client = PRAXClient(ctx)
    pipeline = client.get_pipeline(name, **filters)
    pipeline_fields = [
        RenderField(label='Pipeline Name', path='$.name'),
        RenderField(label='Description', path='$.description'),
        RenderField(label='Project', path='$.project'),
        RenderField(label='Organization', path='$.org'),
        RenderField(label='Stage', path='$.stage'),
        RenderField(label='Schedule', path='$.schedule'),
        RenderField(label='Suspended', path='$.suspended', ),
        RenderField(label='Created At', path='$.created_at', mod=format_dt),
        RenderField(label='Updated At', path='$.updated_at', mod=format_dt),
    ]
    run_fields = [
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
            click.echo("Last Run:")
            click.echo(Renderer(
                data=[pipeline.last_run], 
                fields=run_fields, 
                indent=2
            ).render(output_format='table', tablefmt='plain'))
            if pipeline.last_run.arguments:
                click.echo("    Arguments:")
                click.echo(Renderer(
                    data=[pipeline.last_run.arguments], 
                    fields=[], 
                    indent=4
                ).render(output_format='yaml'))
            if pipeline.last_run.details:
                click.echo("  Run Details:")
                click.echo(Renderer(
                    data=[pipeline.last_run.details], 
                    fields=[], 
                    indent=2
                ).render(output_format='yaml'))

    else:
        click.echo(f" {err} Error fetching pipeline:")
        echoerr(pipeline)
        sys.exit(1)


@submit.command(name='pipeline', help='Submit PRAX Pipeline')
@click.pass_context
@name_argument
@project_org_option
@project_user_option
@project_name_option
@project_stage_option
@click.option('-p','--parameter', help='Pipeline parameters', default=None, type=str, multiple=True)
@login_required
def submit_pipeline(ctx: click.Context, name: str, parameter: list[str]|None, **filters):
    client = PRAXClient(ctx)
    pipeline = client.get_pipeline(name, **filters)
    if isinstance(pipeline, models.ErrorResponse):
        click.echo(f" {err} Error fetching pipeline:")
        echoerr(pipeline)
        sys.exit(1)
    else:
        resp = client.submit_pipeline(name, parse_parameters(parameter), **filters)
        if isinstance(resp, models.ErrorResponse):
            click.echo(f" {err} Error submitting pipeline:")
            echoerr(resp)
            sys.exit(1)
        else:
            click.echo(f"{chk} Pipeline submitted successfully! Run ID: {'N/A' if resp.last_run is None else resp.last_run.name}")

@terminate.command(name='pipeline', help='Terminate PRAX Pipeline')
@click.pass_context
@name_argument
@project_org_option
@project_user_option
@project_name_option
@project_stage_option
@login_required
def terminate_pipeline(ctx: click.Context, name: str, **filters):
    client = PRAXClient(ctx)
    pipeline = client.get_pipeline_run(name, **filters)
    if isinstance(pipeline, models.ErrorResponse):
        click.echo(f" {err} Error fetching pipeline:")
        echoerr(pipeline)
        sys.exit(1)
    else:
        resp = client.terminate_pipeline_run(name, **filters)
        if isinstance(resp, models.ErrorResponse):
            click.echo(f" {err} Error terminating pipeline:")
            echoerr(resp)
            sys.exit(1)
        else:
            click.echo(f"{chk} Pipeline terminated successfully! Run ID: {'N/A' if resp is None else resp.name}")


@retry.command(name='pipeline', help='Retry PRAX Pipeline')
@click.pass_context
@name_argument
@project_org_option
@project_user_option
@project_name_option
@project_stage_option
@login_required
def retry_pipeline(ctx: click.Context, name: str, **filters):
    client = PRAXClient(ctx)
    pipeline = client.get_pipeline_run(name, **filters)
    if isinstance(pipeline, models.ErrorResponse):
        click.echo(f" {err} Error fetching pipeline:")
        echoerr(pipeline)
        sys.exit(1)
    else:
        resp = client.retry_pipeline_run(name, **filters)
        if isinstance(resp, models.ErrorResponse):
            click.echo(f" {err} Error retrying pipeline:")
            echoerr(resp)
            sys.exit(1)
        else:
            click.echo(f"{chk} Pipeline retried successfully! Run ID: {'N/A' if resp is None else resp.name}")

@logs.command(name='pipeline', help='Get the Latest Run PRAX Pipeline logs')
@click.pass_context
@name_argument
@project_org_option
@project_user_option
@project_name_option
@project_stage_option
@click.option('-n','--lines', help='Number of lines to show', default=1000, type=int)
@click.option('-f','--follow', help='Follow logs', default=False, type=bool, is_flag=True)
@login_required
def get_pipeline_logs(ctx: click.Context, name: str, lines: int, follow: bool, **filters):
    client = PRAXClient(ctx)
    pipeline = client.get_pipeline(name, **filters)
    if isinstance(pipeline, models.ErrorResponse):
        click.echo(f" {err} Error fetching pipeline:")
        echoerr(pipeline)
        sys.exit(1)
    if pipeline.last_run is None:
        click.echo(f" {err} No active runs found for pipeline '{name}'!")
        sys.exit(1)

    latest_run = pipeline.last_run
    click.echo(f"Fetching logs for pipeline run: {latest_run.name} ...")
    for line in client.get_pipeline_run_logs(latest_run.name, lines, follow, **filters):
        if isinstance(line, models.ErrorResponse):
            click.echo(f" {err} Error fetching logs:")
            echoerr(line)
            sys.exit(1)
        click.echo(line)

# @stop.command(name='pipeline', help='Stop PRAX Pipeline')
# @click.pass_context
# @name_argument
# @project_org_option
# @project_user_option
# @project_name_option
# @project_stage_option
# @login_required
# def stop_pipeline(ctx: click.Context, name: str, **filters):
#     client = PRAXClient(ctx)
#     pipeline = client.get_pipeline_run(name)
#     if isinstance(pipeline, models.ErrorResponse):
#         click.echo(f" {err} Error fetching pipeline:")
#         echoerr(pipeline)
#         sys.exit(1)
#     else:
#         resp = client.stop_pipeline_run(name, **filters)
#         if isinstance(resp, models.ErrorResponse):
#             click.echo(f" {err} Error stopping pipeline:")
#             echoerr(resp)
#             sys.exit(1)
#         else:
#             click.echo(f"{chk} Pipeline stopped successfully! Run ID: {'N/A' if resp is None else resp.name}")


# @resume.command(name='pipeline', help='Resume PRAX Pipeline')
# @click.pass_context
# @name_argument
# @project_org_option
# @project_user_option
# @project_name_option
# @project_stage_option
# @login_required
# def resume_pipeline(ctx: click.Context, name: str, **filters):
#     client = PRAXClient(ctx)
#     pipeline = client.get_pipeline_run(name)
#     if isinstance(pipeline, models.ErrorResponse):
#         click.echo(f" {err} Error fetching pipeline:")
#         echoerr(pipeline)
#         sys.exit(1)
#     else:
#         resp = client.resume_pipeline_run(name, **filters)
#         if isinstance(resp, models.ErrorResponse):
#             click.echo(f" {err} Error resuming pipeline:")
#             echoerr(resp)
#             sys.exit(1)
#         else:
#             click.echo(f"{chk} Pipeline resumed successfully! Run ID: {'N/A' if resp is None else resp.name}")
