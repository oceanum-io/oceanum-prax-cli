
import os
import yaml
import time
from datetime import timedelta
from pathlib import Path
from typing import Literal, Optional, Type, Iterable

import click
import humanize
import requests
from pydantic import SecretStr, RootModel, Field, model_validator, ValidationError

from oceanum.cli.common.symbols import spin, chk, err, wrn, watch, globe
from . import models
from .utils import format_route_status as _frs

class RevealedSecretStr(RootModel):
    root: Optional[str|SecretStr] = None

    @model_validator(mode='after')
    def validate_revealed_secret_str(self):
        if isinstance(self.root, SecretStr):
            self.root = self.root.get_secret_value()
        return self            
    
class RevealedSecretData(models.SecretData):
    root: Optional[dict[str, RevealedSecretStr]] = None

class RevealedSecretSpec(models.SecretSpec):
    data: Optional[RevealedSecretData] = None

class RevealedSecretsBuildCredentials(models.BuildCredentials):
    password: Optional[RevealedSecretStr] = None

class RevealedSecretsBuildSpec(models.BuildSpec):
    credentials: Optional[RevealedSecretsBuildCredentials] = None

class RevealedSecretsCustomDomainSpec(models.CustomDomainSpec):
    tls_cert: Optional[RevealedSecretStr] = Field(
        default=None, 
        alias='tlsCert'
    )
    tls_key: Optional[RevealedSecretStr] = Field(
        default=None, 
        alias='tlsKey'
    )

class RevealedSecretsRouteSpec(models.ServiceRouteSpec):
    custom_domains: Optional[list[RevealedSecretsCustomDomainSpec]] = Field(
        default=None, 
        alias='customDomains'
    )

class RevealedSecretsServiceSpec(models.ServiceSpec):
    routes: Optional[list[RevealedSecretsRouteSpec]] = None

class RevealedSecretsImageSpec(models.ImageSpec):
    username: Optional[RevealedSecretStr] = None
    password: Optional[RevealedSecretStr] = None

class RevealedSecretsSourceRepositorySpec(models.SourceRepositorySpec):
    token: Optional[RevealedSecretStr] = None

class RevealedSecretProjectResourcesSpec(models.ProjectResourcesSpec):
    secrets: Optional[list[RevealedSecretSpec]] = None
    build: Optional[RevealedSecretsBuildCredentials] = None
    images: Optional[list[RevealedSecretsImageSpec]] = None
    sources: Optional[list[RevealedSecretsSourceRepositorySpec]] = None

class RevealedSecretsProjectSpec(models.ProjectSpec):
    resources: Optional[RevealedSecretProjectResourcesSpec] = None

def dump_with_secrets(spec: models.ProjectSpec) -> dict:
    spec_dict = spec.model_dump(
        exclude_none=True,
        exclude_unset=True,
        by_alias=True,
        mode='python'
    )
    return RevealedSecretsProjectSpec(**spec_dict).model_dump(
        exclude_none=True,
        exclude_unset=True,
        by_alias=True,
        mode='json'
    )


class PRAXClient:
    def __init__(self, ctx: click.Context|None = None, token: str|None = None, service: str|None = None) -> None:
        if ctx is not None:
            if ctx.obj.token:
                self.token = f"Bearer {ctx.obj.token.access_token}"
            else:
                self.token = token or os.getenv('PRAX_API_TOKEN')
                
            if ctx.obj.domain.startswith('oceanum.'):
                self.service = f'https://PRAX.{ctx.obj.domain}/api'
            else:
                self.service = service or os.getenv('PRAX_API_URL')
        
        self.ctx = ctx
        self._lag = 2 # seconds
        self._deploy_start_time = time.time()

    def _request(self, 
        method: Literal['GET', 'POST', 'PUT','DELETE','PATCH'], 
        endpoint,
        **kwargs
    ) -> tuple[requests.Response, models.ErrorResponse|None]:
        assert self.service is not None, 'Service URL is required'
        if self.token is not None:
            headers = kwargs.pop('headers', {})|{
                'Authorization': f'{self.token}'
            }
        else:
            headers = kwargs.pop('headers', {})
        url = f"{self.service.removesuffix('/')}/{endpoint}"
        response = requests.request(method, url, headers=headers, **kwargs)
        return response, self._handle_errors(response)
 
    def _get(self, endpoint, **kwargs) -> tuple[requests.Response, models.ErrorResponse|None]:
        return self._request('GET', endpoint, **kwargs)
    
    def _post(self, endpoint, **kwargs) -> tuple[requests.Response, models.ErrorResponse|None]:
        return self._request('POST', endpoint, **kwargs)
    
    def _patch(self, endpoint, **kwargs) -> tuple[requests.Response, models.ErrorResponse|None]:
        return self._request('PATCH', endpoint, **kwargs)
    
    def _put(self, endpoint, **kwargs) -> tuple[requests.Response, models.ErrorResponse|None]:
        return self._request('PUT', endpoint, **kwargs)
    
    def _delete(self, endpoint, **kwargs) -> tuple[requests.Response, models.ErrorResponse|None]:
        return self._request('DELETE', endpoint, **kwargs)
    
    def _wait_project_commit(self, **params) -> bool:
        while True:
            project = self.get_project(**params)
            if isinstance(project, models.ProjectSchema) and project.last_revision is not None:
                if project.last_revision.status == 'created':
                    time.sleep(self._lag)
                    click.echo(f' {spin} Waiting for Revision #{project.last_revision.number} to be committed...')
                    continue
                elif project.last_revision.status == 'no-change':
                    click.echo(f' {wrn} No changes to commit, exiting...')
                    return False
                elif project.last_revision.status == 'failed':
                    click.echo(f" {err} Revision #{project.last_revision.number} failed to commit, exiting...")
                    return False
                elif project.last_revision.status == 'commited':
                    click.echo(f" {chk} Revision #{project.last_revision.number} committed successfully")
                    return True
            else:
                click.echo(f' {err} No project revision found, exiting...')
                break
        return True
    
    def _wait_stages_start_updating(self, **params):
        counter = 0
        while True:
            project = self.get_project(**params)
            if isinstance(project, models.ProjectSchema):
                updating = any([s.status in ['updating','degraded'] for s in project.stages])
                ready_stages = all([s.status in ['ready', 'error'] for s in project.stages])
                if updating:
                    break
                elif counter > 5 and ready_stages:
                    #click.echo(f"Project '{project.name}' finished being updated in {time.time()-start:.2f}s")
                    break
                else:
                    click.echo(f' {spin} Waiting for project to start updating...')
                    pass
                    time.sleep(self._lag)
                    counter += 1
                return project
            else:
                click.echo(f' {err} Failed to get project details!')
                break
    
    def _wait_builds_to_finish(self, **params):
        def get_builds(project) -> list[models.BuildSchema]:
            builds = self.list_builds(project=project.name, org=project.org)
            if not isinstance(builds, list):
                click.echo(f" {err} Failed to get project builds!")
                return []
            return builds
        
        project = self.get_project(**params)
        
        if isinstance(project, models.ProjectSchema) and project.last_revision is not None:
            params['project'] = params.pop('project_name', project.name)
            
            spec = project.last_revision.spec
            builds = spec.resources.builds if spec.resources else None
            
            if not builds:
                click.echo(f" {chk} No builds found in project '{project.name}'!")
                return True

            click.echo(f" {spin} Checking builds for project '{project.name}'...")
            time.sleep(15)
            while True:
                time.sleep(self._lag)
                project_builds = get_builds(project)
                if not project_builds:
                    continue
                
                finished_builds = [b for b in project_builds if b.last_run and b.last_run.status in ['Succeeded','Failed','Error']]
                running_builds = [b for b in project_builds if b.last_run and b.last_run.status in ['Pending','Running']]
                
                if project_builds == finished_builds:
                    click.echo(f" {chk} All builds finished!")
                    for build in project_builds:
                        if build.last_run and build.last_run.status in ['Failed','Error']:
                            click.echo(f" {err} Build '{build.name}-{build.stage}' failed to start or while running!")
                            click.echo(f"Inspect Build Run logs with 'oceanum prax logs build {build.name} --project {project.name} --org {project.org} --stage {build.stage}' command !")
                            return False
                        elif build.last_run and build.last_run.status == 'Succeeded':
                            click.echo(f" {chk} Build '{build.name}-{build.stage}' finished successfully!")
                    break
                elif running_builds:
                    click.echo(f" {spin} Waiting for builds to finish...")
                    continue
        else:
            click.echo(f" {err} Failed to get project details!")
            return False
        return True
            
    def _wait_stages_finish_updating(self, **params):
        counter = 0
        click.echo(f' {spin} Waiting for all stages to finish updating...')
        while True:
            project = self.get_project(**params)
            if isinstance(project, models.ProjectSchema):
                project_name = project.name if project else 'unknown'
                stages = project.stages if project else []
                updating = any([s.status in ['building'] for s in stages])
                all_finished = all([s.status in ['healthy', 'error'] for s in stages])
                if updating:
                    time.sleep(self._lag)
                    continue
                elif all_finished:
                    click.echo(f" {chk} Project '{project_name}' finished being updated!")
                    break
                else:
                    time.sleep(self._lag)
                    counter += 1
    
    def _check_routes(self, **params):
        project = self.get_project(**params)
        if isinstance(project, models.ProjectSchema):
            project_name = project.name if project else 'unknown'
            for stage in project.stages:
                for route in stage.resources.routes:
                    urls = [f"https://{d}/" for d in route.custom_domains] + [route.url]
                    if route.status == 'error':
                        click.echo(f" {err} Route '{route.name}' at stage '{route.stage}' failed to start!")
                        click.echo(f"Status is {_frs(route.status)}, inspect deployment with 'oceanum PRAX inspect project {project_name}'!")
                    else:
                        s = 's' if len(urls) > 1 else ''
                        click.echo(f" {chk} Route '{route.name}' is {_frs(route.status)} and available at URL{s}:")
                        for url in urls:
                            click.echo(f" {globe} {url}")
        
    def _handle_errors(self, response: requests.Response) -> models.ErrorResponse|None:
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            try:
                return models.ErrorResponse(**response.json())
            except requests.exceptions.JSONDecodeError:
                return models.ErrorResponse(detail=response.text)
            except ValidationError:
                return models.ErrorResponse(detail=response.json())
            except Exception as e:
                return models.ErrorResponse(detail=str(e))
    
    def _run_action(self, 
            action: Literal['submit', 'terminate', 'retry'],
            endpoint: Literal['task', 'pipeline', 'build','task-runs','pipeline-runs','build-runs'],
            run_name: str,
        **params) -> models.StagedRunSchema | models.ErrorResponse:
        action_methods = {
            'terminate': self._put,
            'retry': self._put,
            'submit': self._post
        }
        confirm_status = {
            'submit': 'Pending',
            'terminate': 'Failed',
            'retry': ['Pending', 'Running', 'Failed', 'Error']
        }
        response, errs = action_methods[action](
            f'{endpoint}/{run_name}/{action}', 
            json=params or None, 
            params=params or None
        )
        if errs:
            return errs
        else:
            run = models.StagedRunSchema(**response.json())
            if run.status in confirm_status[action]:
                return run
            else:
                return models.ErrorResponse(detail=f"Failed to {action} run '{run_name}'!")

    def wait_project_deployment(self, **params) -> bool:
        self._deploy_start_time = time.time()
        committed = self._wait_project_commit(**params)
        if committed:
            started_updating = self._wait_stages_start_updating(**params)
            build_succeeded = self._wait_builds_to_finish(**params)
            if build_succeeded:
                self._wait_stages_finish_updating(**params)
                self._check_routes(**params)
            delta = timedelta(seconds=time.time()-self._deploy_start_time)
            with_error = "(with errors) " if not all([committed, started_updating, build_succeeded]) else " "
            click.echo(f" {watch} Deployment finished {with_error}in {humanize.naturaldelta(delta)}.")
        return True
    
    @classmethod
    def load_spec(cls, specfile: str) -> models.ProjectSpec|models.ErrorResponse:
        try:
            with Path(specfile).open() as f:
                spec_dict = yaml.safe_load(f)
            return models.ProjectSpec(**spec_dict)
        except FileNotFoundError:
            return models.ErrorResponse(detail=f"Specfile not found: {specfile}")
        except ValidationError as e:
            return models.ErrorResponse(detail=[
                models.ValidationErrorDetail(
                    loc=[str(v) for v in e['loc']], 
                    msg=e['msg'], 
                    type=e['type']) for e in e.errors()
                ])
    
    def deploy_project(self, spec: models.ProjectSpec) -> models.ProjectSchema | models.ErrorResponse:
        payload = dump_with_secrets(spec)
        response, errs = self._post('projects', json=payload)
        return errs if errs else models.ProjectSchema(**response.json())

    def patch_project(self, project_name: str, ops: list[models.JSONPatchOpSchema]) -> models.ProjectSchema | models.ErrorResponse:
        payload = [op.model_dump(exclude_none=True, mode='json') for op in ops]
        response, errs = self._patch(f'projects/{project_name}', json=payload)
        return errs if errs else models.ProjectSchema(**response.json())
    
    def delete_project(self, project_id: str, **filters) -> str | models.ErrorResponse:
        response, errs = self._delete(f'projects/{project_id}', params=filters or None)
        return errs if errs else "Project deleted successfully!"
    
    def get_users(self) -> list[models.UserSchema] | models.ErrorResponse:
        response, errs = self._get('users')
        if not errs:
            return [models.UserSchema(**user) for user in response.json()]
        return errs
    
    def create_or_update_user_secret(self, secret_name: str, org: str, secret_data: dict, description: str|None = None) -> models.SecretSpec | models.ErrorResponse:
        response, errs = self._post(
            f'users/{org}/resources/secrets', 
            json={
                'name': secret_name, 
                'description': description,
                'data': secret_data
            }
        )
        return errs if errs else models.SecretSpec(**response.json())

    def list_projects(self, **filters) -> list[models.ProjectSchema] | models.ErrorResponse:
        response, errs = self._get('projects', params=filters or None)
        if not errs:
            projects_json = response.json()
            projects = []
            for project in projects_json:
                try:
                    models.ProjectSchema(**project)
                    projects.append(project)
                except Exception as e:
                    click.echo(f"Error: {e}")
                    click.echo(f"Project: {project}")
            return projects
        else:
            return errs
    
    def get_project(self, project_name: str, **filters) -> models.ProjectSchema|models.ErrorResponse:
        """
        Try to get a project by name and org/user filters,
        when the project is not found, print the error message and return None
        """
        response, errs = self._get(f'projects/{project_name}', params=filters or None)
        return errs if errs else models.ProjectSchema(**response.json())
    
    def list_sources(self, **filters) -> list[models.SourceSchema] | models.ErrorResponse:
        response, errs = self._get('sources', params=filters or None)
        if not errs:
            return [models.SourceSchema(**source) for source in response.json()]
        else:
            return errs
    
    def list_tasks(self, **filters) -> list[models.TaskSchema] | models.ErrorResponse:
        response, errs = self._get('tasks', params=filters or None)
        if not errs:
            return [models.TaskSchema(**task) for task in response.json()]
        else:
            return errs
        
    def get_task(self, task_id: str, **filters) -> models.TaskSchema | models.ErrorResponse:
        response, errs = self._get(f'tasks/{task_id}', params=filters or None)
        return errs if errs else models.TaskSchema(**response.json())
    
    def _submit(self, 
            resp_model: Type[models.TaskSchema|models.BuildSchema|models.PipelineSchema],
            name: str, 
            parameters: dict|None, 
            **filters) -> models.TaskSchema | models.BuildSchema | models.PipelineSchema | models.ErrorResponse:
        endpoint = resp_model.__name__.removesuffix('Schema').lower()+"s"
        response, errs = self._post(
            f'{endpoint}/{name}/submit', 
            json={'parameters': parameters} if parameters else None, 
            params=filters or None
        )
        return errs if errs else resp_model(**response.json())
    
    def submit_task(self, task_name: str, parameters: dict|None, **filters) -> models.TaskSchema | models.ErrorResponse:
        task = self._submit(models.TaskSchema, task_name, parameters, **filters)
        if isinstance(task, models.TaskSchema):
            return task
        elif isinstance(task, models.ErrorResponse):
            return task
        else:
            return models.ErrorResponse(detail="Failed to submit task!")
    
    def get_task_run(self, run_name: str, **filters) -> models.StagedRunSchema | models.ErrorResponse:
        response, errs = self._get(f'task-runs/{run_name}', params=filters or None)
        return errs if errs else models.StagedRunSchema(**response.json())
    
    def terminate_task_run(self, run_name: str, **filters) -> models.StagedRunSchema | models.ErrorResponse:
        response, errs = self._put(f'task-runs/{run_name}/terminate', params=filters or None)
        return errs if errs else models.StagedRunSchema(**response.json())
    
    def retry_task_run(self, run_name: str, **filters) -> models.StagedRunSchema | models.ErrorResponse:
        response, errs = self._put(f'task-runs/{run_name}/retry', params=filters or None)
        return errs if errs else models.StagedRunSchema(**response.json())

    def list_pipelines(self, **filters) -> list[models.PipelineSchema] | models.ErrorResponse:
        response, errs = self._get('pipelines', params=filters or None)
        if not errs:
            return [models.PipelineSchema(**pipeline) for pipeline in response.json()]
        else:
            return errs
        
    def get_pipeline(self, pipeline_name: str, **filters) -> models.PipelineSchema | models.ErrorResponse:
        response, errs = self._get(f'pipelines/{pipeline_name}', params=filters or None)
        return errs if errs else models.PipelineSchema(**response.json())
    
    def submit_pipeline(self, pipeline_name: str, parameters: dict|None=None, **filters) -> models.PipelineSchema | models.ErrorResponse:
        pipeline = self._submit(models.PipelineSchema, pipeline_name, parameters, **filters)
        if isinstance(pipeline, models.PipelineSchema):
            return pipeline
        elif isinstance(pipeline, models.ErrorResponse):
            return pipeline
        else:
            return models.ErrorResponse(detail="Failed to submit pipeline!")
    
    def get_pipeline_run(self, run_name: str, **filters) -> models.StagedRunSchema | models.ErrorResponse:
        response, errs = self._get(f'pipeline-runs/{run_name}', params=filters or None)
        return errs if errs else models.StagedRunSchema(**response.json())
    
    def terminate_pipeline_run(self, run_name: str, **filters) -> models.StagedRunSchema | models.ErrorResponse:
        response, errs = self._put(f'pipeline-runs/{run_name}/terminate', params=filters or None)
        return errs if errs else models.StagedRunSchema(**response.json())
    
    def stop_pipeline_run(self, run_name: str, **filters) -> models.StagedRunSchema | models.ErrorResponse:
        response, errs = self._put(f'pipeline-runs/{run_name}/stop', params=filters or None)
        return errs if errs else models.StagedRunSchema(**response.json())
    
    def resume_pipeline_run(self, run_name: str, **filters) -> models.StagedRunSchema | models.ErrorResponse:
        response, errs = self._put(f'pipeline-runs/{run_name}/resume', params=filters or None)
        return errs if errs else models.StagedRunSchema(**response.json())
    
    def retry_pipeline_run(self, run_name: str, **filters) -> models.StagedRunSchema | models.ErrorResponse:
        response, errs = self._put(f'pipeline-runs/{run_name}/retry', params=filters or None)
        return errs if errs else models.StagedRunSchema(**response.json())

    def list_builds(self, **filters) -> list[models.BuildSchema] | models.ErrorResponse:
        response, errs = self._get('builds', params=filters or None)
        return errs if errs else [models.BuildSchema(**build) for build in response.json()]
    
    def get_build(self, build_name: str, **filters) -> models.BuildSchema | models.ErrorResponse:
        response, errs = self._get(f'builds/{build_name}', params=filters or None)
        return errs if errs else models.BuildSchema(**response.json())
    
    def submit_build(self, build_name: str, parameters: dict|None=None,  **filters) -> models.BuildSchema | models.ErrorResponse:
        build = self._submit(models.BuildSchema, build_name, parameters, **filters)
        if isinstance(build, models.BuildSchema):
            return build
        elif isinstance(build, models.ErrorResponse):
            return build
        else:
            return models.ErrorResponse(detail="Failed to submit build!")
    
    def get_build_run(self, run_name: str, **filters) -> models.StagedRunSchema | models.ErrorResponse:
        response, errs = self._get(f'build-runs/{run_name}', params=filters or None)
        return errs if errs else models.StagedRunSchema(**response.json())
    
    def terminate_build_run(self, run_name: str, **filters) -> models.StagedRunSchema | models.ErrorResponse:
        response, errs = self._put(f'build-runs/{run_name}/terminate', params=filters or None)
        return errs if errs else models.StagedRunSchema(**response.json())
    
    def retry_build_run(self, run_name: str, **filters) -> models.StagedRunSchema | models.ErrorResponse:
        response, errs = self._put(f'build-runs/{run_name}/retry', params=filters or None)
        return errs if errs else models.StagedRunSchema(**response.json())
    
    def list_routes(self, **filters) -> list[models.RouteSchema] | models.ErrorResponse:
        response, errs = self._get('routes', params=filters or None)
        if not errs:
            return [models.RouteSchema(**route) for route in response.json()]
        else:
            return errs
    
    def get_route(self, route_name: str) -> models.RouteSchema | models.ErrorResponse:
        response, errs = self._get(f'routes/{route_name}')
        return errs if errs else models.RouteSchema(**response.json())
    
    def get_build_run_logs(self, run_name: str, lines: int, follow: bool, **filters) -> Iterable[str|models.ErrorResponse]:
        filters['follow'] = follow
        filters['tail'] = lines
        response, errs = self._get(
            f'build-runs/{run_name}/logs', 
            params=filters or None,
            stream=True
        )
        if response.ok:
            for line in response.iter_lines():
                yield line
        else:
            yield errs if errs else models.ErrorResponse(detail=response.text)


    def get_task_run_logs(self, run_name: str, lines: int, follow: bool, **filters) -> Iterable[str|models.ErrorResponse]:
        filters['follow'] = follow
        filters['tail'] = lines
        response, errs = self._get(
            f'task-runs/{run_name}/logs', 
            params=filters or None,
            stream=True
        )
        if response.ok:
            for line in response.iter_lines():
                yield line
        else:
            yield errs if errs else models.ErrorResponse(detail=response.text)

    def get_pipeline_run_logs(self, run_name: str, lines: int, follow: bool, **filters) -> Iterable[str|models.ErrorResponse]:
        filters['follow'] = follow
        filters['tail'] = lines
        response, errs = self._get(
            f'pipeline-runs/{run_name}/logs', 
            params=filters or None,
            stream=True
        )
        if response.ok:
            for line in response.iter_lines():
                yield line
        else:
            yield errs if errs else models.ErrorResponse(detail=response.text)
    
    def get_route_logs(self, route_name: str, lines: int, follow: bool, **filters) -> Iterable[str|models.ErrorResponse]:
        filters['follow'] = follow
        filters['tail'] = lines
        response, errs = self._get(
            f'routes/{route_name}/logs', 
            params=filters or None,
            stream=True
        )
        if response.ok:
            for line in response.iter_lines():
                yield line
        else:
            yield errs if errs else models.ErrorResponse(detail=response.text)
        
    
    def update_route_thumbnail(self, route_name: str, thumbnail: click.File) -> models.RouteSchema | models.ErrorResponse:
        files = {'thumbnail': thumbnail}
        response, errs = self._post(f'routes/{route_name}/thumbnail', files=files)
        return errs if errs else models.RouteSchema(**response.json())
    
    def validate(self, specfile: str) -> models.ProjectSpec | models.ErrorResponse:
        resp = self.load_spec(specfile)
        if isinstance(resp, models.ErrorResponse):
            return resp
        else:
            spec_dict = resp.model_dump(
                exclude_none=True,
                exclude_unset=True,
                by_alias=True,
                mode='json'
            )
            response, errs = self._post('validate', json=spec_dict)
            return errs if errs else models.ProjectSpec(**response.json())
        
    def allow_project(self, 
        project_name: str, 
        permissions: models.ResourcePermissionsSchema, 
        **filters
    ) -> models.ResourcePermissionsSchema | models.ErrorResponse:
        response, errs = self._post(
            f'projects/{project_name}/permissions',
            params=filters or None, 
            json=permissions.model_dump()
        )
        return errs if errs else models.ResourcePermissionsSchema(**response.json())
    
    def allow_route(self, 
        route_name: str, 
        permissions: models.ResourcePermissionsSchema, 
        **filters
    ) -> models.ResourcePermissionsSchema | models.ErrorResponse:
        response, errs = self._post(
            f'routes/{route_name}/permissions',
            params=filters or None, 
            json=permissions.model_dump()
        )
        return errs if errs else models.ResourcePermissionsSchema(**response.json())