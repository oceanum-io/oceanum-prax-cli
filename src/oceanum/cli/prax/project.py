import sys
from os import linesep

import click

from oceanum.cli.common.renderer import Renderer, RenderField
from oceanum.cli.common.utils import format_dt
from oceanum.cli.auth import login_required
from oceanum.cli.common.symbols import spin, chk, err, wrn, info, key

from .client import PRAXClient
from .main import list_group, describe, delete, prax, update, allow
from . import models
from .utils import (
    echoerr, merge_secrets,
    project_status_color as psc,
    stage_status_color as ssc,
    source_status_color as sosc,
)

name_argument = click.argument('name', type=str)
name_option = click.option('--name', help='Set the resource name', required=False, type=str)
project_name_option = click.option('--project', help='Set Project Name', required=False, type=str)
project_org_option = click.option('--org', help='Set Project Organization', required=False, type=str)
project_user_option = click.option('--user', help='Set Project Owner email', required=False, type=str)
project_stage_option = click.option('--stage', help='Set Project Stage', required=False, type=str)

@list_group.command(name='projects', help='List PRAX Projects')
@click.pass_context
@click.option('--search', help='Search by project name or description', default=None, type=str)
@click.option('--status', help='filter by Project status', default=None, type=str)
@project_org_option
@project_user_option
@login_required
def list_projects(ctx: click.Context, search: str|None, org: str|None, user: str|None, status: str|None):
    click.echo(f' {spin} Listing projects...')
    client = PRAXClient(ctx)
    filters = {
        'search': search,
        'org': org,
        'user': user,
        'status': status
    }
    projects = client.list_projects(**{
        k: v for k, v in filters.items() if v is not None
    })

    fields = [
        RenderField(label='Name', path='$.name'),
        RenderField(label='Org.', path='$.org'),
        RenderField(label='Rev.', path='$.last_revision.number'),
        RenderField(label='Status', path='$.status', mod=psc),
        RenderField(label='Stages', path='$.stages.*', mod=ssc),
    ]
        
    if not projects:
        click.echo(f' {wrn} No projects found!')
        sys.exit(1)
    elif isinstance(projects, models.ErrorResponse):
        click.echo(f" {err} Could not list projects!")
        echoerr(projects)
        sys.exit(1)
    else:
        click.echo(Renderer(data=projects, fields=fields).render(output_format='table'))

@prax.command(name='validate', help='Validate PRAX Project Specfile')
@click.argument('specfile', type=click.Path(exists=True))
@click.pass_context
@login_required
def validate_project(ctx: click.Context, specfile: click.Path):
    click.echo(f' {spin} Validating PRAX Project Spec file...')
    client = PRAXClient(ctx)
    response = client.validate(str(specfile))
    if isinstance(response, models.ErrorResponse):
        click.echo(f" {err} Validation failed!")
        echoerr(response)
        sys.exit(1)
    else:
        click.echo(f' {chk} OK! Project Spec file is valid!')

@prax.command(name='deploy', help='Deploy a PRAX Project Specfile')
@name_option
@project_org_option
@project_user_option
@click.option('--wait', help='Wait for project to be deployed', default=True)
# Add option to allow passing secrets to the specfile, this will be used to replace placeholders
# can be multiple, e.g. --secret secret-1:key1=value1,key2=value2 --secret secret-2:key2=value2
@click.option('-s','--secrets',help='Replace existing secret data values, i.e secret-name:key1=value1,key2=value2', multiple=True)
@click.argument('specfile', type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@click.pass_context
@login_required
def deploy_project(
    ctx: click.Context, 
    specfile: click.Path,
    name: str|None,
    org: str|None, 
    user: str|None,
    wait: bool,
    secrets: list[str]
):

    client = PRAXClient(ctx)
    project_spec = client.load_spec(str(specfile))
    if isinstance(project_spec, models.ErrorResponse):
        click.echo(f" {err} Failed to load project spec file!")
        echoerr(project_spec)
        sys.exit(1)

    if name is not None:
        project_spec.name = name
    if org is not None:
        project_spec.user_ref = models.UserRef(org)
    if user is not None:
        project_spec.member_ref = user

    if secrets:
        click.echo(f' {key} Parsing and merging secrets...')
        project_spec = merge_secrets(project_spec, secrets)

    user_org = getattr(project_spec.user_ref, 'root', None) or ctx.obj.token.active_org
    user_email = project_spec.member_ref or ctx.obj.token.email

    get_params = {
        'project_name': project_spec.name,
        'org': user_org,
        'user': user_email
    }
    project = client.get_project(**get_params)
    click.echo(f'Using domain: {ctx.obj.token.domain}')
    click.echo(f'')
    
    if isinstance(project, models.ProjectDetailsSchema):
        click.echo(f" {spin} Updating existing PRAX Project:")
    else:
        if 'not found' in str(project.detail).lower():
            click.echo(f" {spin} Deploying NEW PRAX Project:")
        else:
            click.echo(f" {err} Could not deploy project!")
            echoerr(project)
            sys.exit(1)

    click.echo()
    click.echo(f'  Project Name: {project_spec.name}')
    click.echo(f"  Organization: {user_org}")
    click.echo(f'  Owner:        {user_email}')
    click.echo()
    click.echo('Safe to Ctrl+C at any time...')
    click.echo()
    project = client.deploy_project(project_spec)
    if isinstance(project, models.ErrorResponse):
        click.echo(f" {err} Deployment failed!")
        click.echo(f" {wrn} {project.detail}")
        sys.exit(1)
    project = client.get_project(**get_params)
    if isinstance(project, models.ProjectDetailsSchema) and project.last_revision is not None:
        click.echo(f" {chk} Revision #{project.last_revision.number} created successfully!")
        if wait:
            click.echo(f' {spin} Waiting for project to be deployed...')
            client.wait_project_deployment(**get_params)
    else:
        click.echo(f" {err} Could not retrieve project details!")
        click.echo(f" {wrn} Please check the project status in the PRAX console!")

@delete.command(name='project')
@click.argument('project_name', type=str)
@project_org_option
@project_user_option
@click.pass_context
@login_required
def delete_project(ctx: click.Context, project_name: str, org: str|None, user:str|None):
    client = PRAXClient(ctx)
    project = client.get_project(project_name, org=org, user=user)
    if isinstance(project, models.ProjectDetailsSchema):
        click.confirm(
            f"Deleting project:{linesep}"\
            f"{linesep}"\
            f"Project Name: {project_name}{linesep}"\
            f"Org: {project.org}{linesep}"\
            f"Owner: {project.owner}{linesep}"\
            f"{linesep}"\
            "This will attempt to remove all deployed resources for this project! Are you sure?",
            abort=True
        )
        response = client.delete_project(project_name, org=org, user=user)
        if isinstance(response, models.ErrorResponse):
            click.echo(f" {err} Failed to delete existing project!")
            echoerr(response)
            sys.exit(1)
        else:
            click.echo(f' {chk} Project {project_name} deleted successfuly!')
            click.echo(f' {info} Deployed resources will be removed shortly...')
    else:
        click.echo(f" {err} Failed to delete project '{project_name}'!")
        echoerr(project)
        sys.exit(1)

@describe.command(name='project', help='Describe a PRAX Project')
@click.option('--show-spec', help='Show project spec', default=False, type=bool, is_flag=True)
@click.option('--only-spec', help='Show only project spec', default=False, type=bool, is_flag=True)
@click.argument('project_name', type=str)
@project_org_option
@project_user_option
@click.pass_context
@login_required
def describe_project(ctx: click.Context, project_name: str, org: str, user:str, show_spec: bool=False, only_spec: bool=False):
    client = PRAXClient(ctx)
    project = client.get_project(project_name, org=org, user=user)
    last_revision = project.last_revision if isinstance(project, models.ProjectDetailsSchema) else None
    project_spec = last_revision.spec if last_revision is not None else None
    click.echo()

    def render_revision(revision: models.RevisionDetailsSchema):
        revision_fields = [
            RenderField(label='Revision', path='$.number'),
            RenderField(label='Author', path='$.author'),
            RenderField(label='Status', path='$.status'),
            RenderField(label='Created At', path='$.created_at', mod=format_dt),
        ]

        click.echo(Renderer(
            data=[revision], 
            fields=revision_fields, 
            indent=2
        ).render(output_format='table', tablefmt='plain'))
        # click.echo(' '*2+'Spec:')
        # click.echo(Renderer(
        #     data=[revision.spec], 
        #     fields=[], 
        #     indent=4
        # ).render(output_format='yaml'))

    def render_stage_resources(resources: models.StageResourcesSchema):    

        def render_resources(
            resources: list[models.BuildSchema]|list[models.PipelineSchema]|list[models.RouteSchema]|list[models.TaskSchema],
            extra_fields: list[RenderField],
            indent: int = 6
        ):
            resource_type = resources[0].__class__.__name__.removesuffix('Schema').title()+'s'
            click.echo(' '*max(0,indent-2)+f'{resource_type}:')
            for resource in resources:
                common_fields = [
                    RenderField(label='Project Name', path='$.name'),
                    RenderField(label='Description', path='$.description'),
                    #RenderField(label='Object Ref.', path='$.object_ref'),
                    RenderField(label='Updated At', path='$.updated_at', mod=format_dt),
                    
                ]
                click.echo(Renderer(
                    data=[resource],
                    fields=common_fields+extra_fields,
                    indent=indent
                ).render(output_format='table', tablefmt='plain'))
                if len(resources) > 1:
                    click.echo(' '*indent+'-'*40)
            click.echo()
        
        pipeline_fields = [
            RenderField(label='Last Run Status', 
                        path='$.last_run', 
                        mod=lambda x: x['status'] if x is not None else 'N/A'
            ),
        ]

        if resources.builds:
            build_fields = [
                RenderField(label='Source Ref', path='$.source_ref'),
                RenderField(label='Commit', path='$.commit_sha'),
                RenderField(label='Image digest', path='$.image_digest'),            
            ]+pipeline_fields
            render_resources(resources.builds, build_fields, indent=6)

        if resources.routes:
            route_fields = [
                RenderField(label='Route Status', path='$.status'),
            ]
            render_resources(resources.routes, route_fields, indent=6)

        if resources.tasks:
            render_resources(resources.tasks, pipeline_fields, indent=6)
                
        if resources.pipelines:
            render_resources(resources.pipelines, pipeline_fields, indent=6)

    def render_stage(stage: models.StageDetailsSchema):
        stage_fields = [
            RenderField(label='Stage Name', path='$.name'),
            RenderField(label='Status', path='$.status'),
            RenderField(label='Updated At', path='$.updated_at', sep=linesep, mod=format_dt),
            RenderField(label='Message', path='$.error_message', sep=linesep),
        ]
        click.echo(Renderer(
            data=[stage], 
            fields=stage_fields, 
            indent=2
        ).render(output_format='table', tablefmt='plain'))
        click.echo(' '*2+'Deployed Resources:')
        render_stage_resources(stage.resources)

    if isinstance(project, models.ProjectDetailsSchema) and project_spec is not None:
        render_fields = [
            RenderField(label='Resource Name', path='$.name'),
            RenderField(label='Description', path='$.description'),
            RenderField(label='Organisation', path='$.org'),
            RenderField(label='Owner', path='$.owner'),
            RenderField(label='Created', path='$.created_at', mod=format_dt),
        ]
        # 
        click.echo('-'*40)
        click.echo(Renderer(
            data=[project], 
            fields=render_fields
        ).render(output_format='table', tablefmt='plain'))
        if project.last_revision is not None:
            click.echo("Latest Revision:")
            render_revision(project.last_revision)
        click.echo('Stages:')
        for stage in project.stages:
            render_stage(stage)
    else:
        click.echo(f"Project '{project_name}' does not have any revisions!")

    if isinstance(project, models.ErrorResponse):
        click.echo(f" {err} Could not describe project!")
        echoerr(project)
        sys.exit(1)

@update.command(name='project', help='Update Project parameters')
@click.argument('project_name', type=str)
@project_org_option
@project_user_option
@click.option('--description', help='Update project description', default=None, type=str)
@click.option('--active', help='Update project status', default=None, type=bool)
@click.pass_context
def update_project(ctx: click.Context, project_name: str, description: str, org: str, user:str, active: bool):
    client = PRAXClient(ctx)
    project = client.get_project(project_name, org=org, user=user)
    ops = []
    if isinstance(project, models.ProjectDetailsSchema):
        project.description = description
        if description:
            ops.append(models.JSONPatchOpSchema(
                op=models.Op('replace'),
                path='/description',
                value=description
            ))
        if active is not None:
            ops.append(models.JSONPatchOpSchema(
                op=models.Op('replace'),
                path='/active',
                value=active
            ))
        project = client.patch_project(project.name, ops)
        if isinstance(project, models.ProjectDetailsSchema):
            click.echo(f"Project '{project_name}' description updated!")

    if isinstance(project, models.ErrorResponse):
        click.echo(f" {err} Failed to update project description!")
        echoerr(project)
        sys.exit(1)
        

@allow.command(name='project')
@click.argument('project_name', type=str, required=True)
@project_org_option
@project_user_option
@click.option('-g','--group', type=str, required=False, multiple=True)
@click.option('-u','--user', type=str, required=False, multiple=True)
@click.option('-a','--assign', help='Allow to assign project permissions', default=None, type=bool, is_flag=True)
@click.option('-v','--view', help='Allow to view the project', default=None, type=bool, is_flag=True)
@click.option('-c','--change', help='Allow to change the project, implies --view', default=None, type=bool, is_flag=True)
@click.option('-d','--delete', help='Allow to delete the project, implies --view and --change', default=None, type=bool, is_flag=True)
@click.pass_context
def allow_project(ctx: click.Context, project_name: str, org: str, group: list[str],
                  user: list[str], assign: bool, view: bool, change: bool, 
                  delete: bool):
    
    def _get_perm(subject: str):
        return models.PermissionsSchema(
            subject=subject,
            view=view if view is not None else None,
            change=change if change is not None else None,
            assign=assign if assign is not None else None,
            delete=delete if delete is not None else None
        )

    client = PRAXClient(ctx)
    response = client.get_project(project_name, org=org, user=user)
    if isinstance(response, models.ProjectDetailsSchema):
        permissions = models.ResourcePermissionsSchema(
            groups=[_get_perm(g) for g in group],
            users=[_get_perm(u) for u in user],
        )
        response = client.allow_project(response.name, permissions)
        if not isinstance(response, models.ErrorResponse):
            click.echo(f"{chk} Permissions for project '{project_name}' set successfully!")
            click.echo(f"{info} {response}")
    if isinstance(response, models.ErrorResponse):
        click.echo(f" {err} Failed to grant permission to project!")
        echoerr(response)
        sys.exit(1)

@list_group.command(name='sources', help='List PRAX Project Sources')
@click.pass_context
@project_name_option
@project_org_option
@project_user_option
@click.option('--search', help='Search by project name or description', default=None, type=str)
@click.option('--status', help='filter by Project status', default=None, type=str)
def list_sources(ctx: click.Context, project: str|None, org: str|None, 
                 user: str|None, search: str|None, status: str|None):
    click.echo(f' {spin} Listing sources...')
    client = PRAXClient(ctx)
    filters = {
        'search': search,
        'project': project,
        'org': org,
        'user': user,
        'status': status,
    }
    sources = client.list_sources(**filters)

    fields = [
        RenderField(label='Name', path='$.name'),
        RenderField(label='Org.', path='$.org'),
        RenderField(label='Project', path='$project'),
        RenderField(label='Stage', path='$.stage'),
        RenderField(label='Type', path='$.source_type', mod=lambda x: x.title()),
        RenderField(label='Repository', path='$.repository'),
        RenderField(label='Status', path='$.status', mod=sosc),
    ]
        
    if not sources:
        click.echo(f' {wrn} No sources found!')
        sys.exit(1)
    elif isinstance(sources, models.ErrorResponse):
        click.echo(f" {err} Could not list sources!")
        echoerr(sources)
        sys.exit(1)
    else:
        click.echo(Renderer(data=sources, fields=fields).render(output_format='table'))