
import os
import yaml
import time
from datetime import timedelta
from pathlib import Path
from typing import Literal, Optional, Type, Iterable, Any

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
        schema: Type[models.BaseModel]|None = None,
        **kwargs
    ) -> tuple[Any|requests.Response, models.ErrorResponse|None]:
        assert self.service is not None, 'Service URL is required'
        if self.token is not None:
            headers = kwargs.pop('headers', {})|{
                'Authorization': f'{self.token}'
            }
        else:
            headers = kwargs.pop('headers', {})
        url = f"{self.service.removesuffix('/')}/{endpoint}"
        response = requests.request(method, url, headers=headers, **kwargs)
        errs = self._handle_errors(response)
        obj = None
        if not errs and schema is not None:
            obj = self._validate_schema(response, schema)
        return obj if obj is not None else response,  errs
    
    def _wait_project_commit(self, **params) -> bool:
        while True:
            project = self.get_project(**params)
            if isinstance(project, models.ProjectDetailsSchema) and project.last_revision is not None:
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
            if isinstance(project, models.ProjectDetailsSchema):
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
        
        if isinstance(project, models.ProjectDetailsSchema) and project.last_revision is not None:
            params['project'] = params.pop('project_name', project.name)
            
            spec = project.last_revision.spec
            builds = spec.resources.builds if spec.resources else None
            
            if not builds:
                return True

            click.echo(f" {spin} Waiting for build-run status...")
            time.sleep(10)
            to_finish_msg = False
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
                    if not to_finish_msg:
                        click.echo(f" {spin} Waiting for builds to finish, this can take several minutes...")
                        to_finish_msg = True
                    continue
        else:
            click.echo(f" {err} Failed to get project details!")
            return False
        return True
            
    def _wait_stages_finish_updating(self, **params):
        counter = 0
        click.echo(f' {spin} Waiting for all stages to finish updating...')
        while True:
            counter += 1
            project = self.get_project(**params)
            if isinstance(project, models.ProjectDetailsSchema):
                project_name = project.name if project else 'unknown'
                stages = project.stages or []
                all_finished = all([s.status in ['healthy', 'error'] for s in stages])
                if all_finished:
                    click.echo(f" {chk} Project '{project_name}' finished being updated!")
                    break
                elif counter > 10:
                    routes_error = False
                    # Check for routes with errors
                    for stage in stages:
                        if stage.resources:
                            for route in stage.resources.routes:
                                if getattr(route.next_revision_status,'root',route.next_revision_status) in ['error']:
                                    click.echo(f" {err} Route '{route.name}' at revision #{project.last_revision.number} failed to start!")
                                    msg = (route.details or {}).get('message', 'No error message provided')
                                    click.echo(f" {wrn} See container error details:{os.linesep}{os.linesep}{msg}")
                                    routes_error = True
                    if routes_error:
                        break
                else:
                    time.sleep(self._lag)

    def _check_routes(self, **params):
        project = self.get_project(**params)
        if isinstance(project, models.ProjectDetailsSchema):
            project_name = project.name if project else 'unknown'
            for stage in project.stages:
                for route in stage.resources.routes:
                    urls = [f"https://{d}" for d in route.custom_domains] + [route.url]
                    if route.next_revision_status and str(route.next_revision_status) in ['error']:
                        click.echo(f" {err} Route '{route.name}' at revision #{project.last_revision.number} failed to start!")
                        if route.details:
                            msg = route.details.get('message', 'No error message provided')
                        else:
                            msg = 'No error details provided'
                        click.echo(f" {wrn} Error details:{os.linesep}{os.linesep}{msg}")
                    if route.status in ['online', 'offline']:
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
        except requests.exceptions.RequestException as e:
            return models.ErrorResponse(detail=str(e))
        except Exception as e:
            return models.ErrorResponse(detail=str(e))
        
    
    def _run_action(self, 
            action: Literal['submit', 'terminate', 'retry'],
            endpoint: Literal['task', 'pipeline', 'build','task-runs','pipeline-runs','build-runs'],
            run_name: str,
        **params) -> models.StagedRunSchema | models.ErrorResponse:
        confirm_status = {
            'submit': 'Pending',
            'terminate': 'Failed',
            'retry': ['Pending', 'Running', 'Failed', 'Error']
        }
        obj, errs = self._request(
            'PUT' if action in ['terminate', 'retry'] else 'POST',
            f'{endpoint}/{run_name}/{action}', 
            json=params or None, 
            params=params or None,
            schema=models.StagedRunSchema
        )
        if errs:
            return errs
        elif isinstance(obj, models.StagedRunSchema):
            if obj.status in confirm_status[action]:
                return obj
            else:
                return models.ErrorResponse(detail=f"Failed to {action} run '{run_name}'!")
        else:
            return models.ErrorResponse(detail=f"Failed to {action} run '{run_name}'!")
        
    def _submit(self, 
            resp_model: Type[models.TaskSchema|models.BuildSchema|models.PipelineSchema],
            name: str, 
            parameters: dict|None, 
            **filters) -> models.TaskSchema | models.BuildSchema | models.PipelineSchema | models.ErrorResponse:
        endpoint = resp_model.__name__.removesuffix('Schema').lower()+"s"
        obj, errs = self._request('POST',
            f'{endpoint}/{name}/submit', 
            json={'parameters': parameters} if parameters else None, 
            params=filters or None,
            schema=resp_model
        )
        if isinstance(obj, resp_model):
            return obj
        elif errs:
            return errs
        else:
            return models.ErrorResponse(detail=f"Failed to submit {endpoint} '{name}'!")
    
    def _validate_schema(self, 
        response: requests.Response, 
        schema: Type[Any]
    ) -> Any | models.ErrorResponse:
        try:
            json_data = response.json()
            if isinstance(json_data, list):
                return [schema(**item) for item in json_data]
            else:
                return schema(**response.json())
        except requests.exceptions.JSONDecodeError:
            click.echo(f" {err} API Response Error: {response.text}")
            if self.ctx:
                self.ctx.exit(1)
            return models.ErrorResponse(detail=response.text)
        except ValidationError as e:
            click.echo(f" {err} API Validation Error")
            click.echo(f" {wrn} This may be due to an outdated version of the client library, {os.linesep}"
                       "please try update with \"pip install -U oceanum-prax\" and try again!")
            if self.ctx:
                self.ctx.exit(1)
            return models.ErrorResponse(detail=[
                models.ValidationErrorDetail(
                    loc=[str(v) for v in e['loc']], 
                    msg=e['msg'], 
                    type=e['type']) for e in e.errors()
                ])

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
            click.echo(f" {watch} Deployment finished {humanize.naturaldelta(delta)}.")
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
    
    def list_projects(self, **filters) -> list[models.ProjectItemSchema] | models.ErrorResponse:
        obj, errs = self._request('GET', 'projects', params=filters or None, schema=models.ProjectItemSchema)
        list_projects_err = models.ErrorResponse(detail="Failed to list projects!")
        return obj if isinstance(obj, list) else errs or list_projects_err        
    
    def get_project(self, project_name: str, **filters) -> models.ProjectDetailsSchema|models.ErrorResponse:
        """
        Try to get a project by name and org/user filters,
        when the project is not found, print the error message and return None
        """
        obj, errs = self._request('GET', f'projects/{project_name}', 
                                  params=filters or None, schema=models.ProjectDetailsSchema)
        get_project_err = models.ErrorResponse(detail=f"Failed to get project '{project_name}'!")
        return obj if isinstance(obj, models.ProjectDetailsSchema) else errs or get_project_err
    
    def deploy_project(self, spec: models.ProjectSpec) -> models.ProjectDetailsSchema | models.ErrorResponse:
        payload = dump_with_secrets(spec)
        obj, errs = self._request('POST', 'projects', json=payload, schema=models.ProjectDetailsSchema)
        deploy_err = models.ErrorResponse(detail="Failed to deploy project!")
        return obj if isinstance(obj, models.ProjectDetailsSchema) else errs or deploy_err

    def patch_project(self, project_name: str, ops: list[models.JSONPatchOpSchema]) -> models.ProjectDetailsSchema | models.ErrorResponse:
        payload = [op.model_dump(exclude_none=True, mode='json') for op in ops]
        obj, errs = self._request('PATCH', f'projects/{project_name}', json=payload, schema=models.ProjectDetailsSchema)
        patch_err = models.ErrorResponse(detail="Failed to patch project!")
        return obj if isinstance(obj, models.ProjectDetailsSchema) else errs or patch_err
    
    def delete_project(self, project_id: str, **filters) -> str | models.ErrorResponse:
        _, errs = self._request('DELETE', f'projects/{project_id}', params=filters or None)
        return errs if errs else "Project deleted successfully!"
    
    # USER METHODS
    
    def get_users(self) -> list[models.UserSchema] | models.ErrorResponse:
        obj, errs = self._request('GET', 'users', schema=models.UserSchema, params=None)
        get_users_err = models.ErrorResponse(detail="Failed to get users!")
        return obj if isinstance(obj, list) else errs or get_users_err
    
    def create_or_update_user_secret(self, secret_name: str, org: str, secret_data: dict, description: str|None = None) -> models.SecretSpec | models.ErrorResponse:
        obj, errs = self._request('POST',
            f'users/{org}/resources/secrets', 
            json={
                'name': secret_name, 
                'description': description,
                'data': secret_data
            },
            schema=models.SecretSpec
        )
        secret_err = models.ErrorResponse(detail="Failed to create or update user secret!")
        return obj if isinstance(obj, models.SecretSpec) else errs or secret_err




    def list_sources(self, **filters) -> list[models.SourceSchema] | models.ErrorResponse:
        obj, errs = self._request('GET', 'sources', params=filters or None, schema=models.SourceSchema)
        list_sources_err = models.ErrorResponse(detail="Failed to list sources!")
        return obj if isinstance(obj, list) else errs or list_sources_err
    
    def list_tasks(self, **filters) -> list[models.TaskSchema] | models.ErrorResponse:
        obj, errs = self._request('GET', 'tasks', params=filters or None, schema=models.TaskSchema)
        list_tasks_err = models.ErrorResponse(detail="Failed to list tasks!")
        return obj if isinstance(obj, list) else errs or list_tasks_err
        
    def get_task(self, task_id: str, **filters) -> models.TaskSchema | models.ErrorResponse:
        obj, errs = self._request('GET', f'tasks/{task_id}', params=filters or None, schema=models.TaskSchema)
        get_task_err = models.ErrorResponse(detail=f"Failed to get task '{task_id}'!")
        return obj if isinstance(obj, models.TaskSchema) else errs or get_task_err
    
    def submit_task(self, task_name: str, parameters: dict|None, **filters) -> models.TaskSchema | models.ErrorResponse:
        task = self._submit(models.TaskSchema, task_name, parameters, **filters)
        if isinstance(task, models.TaskSchema):
            return task
        elif isinstance(task, models.ErrorResponse):
            return task
        else:
            return models.ErrorResponse(detail="Failed to submit task!")
    
    def get_task_run(self, run_name: str, **filters) -> models.StagedRunSchema | models.ErrorResponse:
        obj, errs = self._request('GET', f'task-runs/{run_name}', params=filters or None, schema=models.StagedRunSchema)
        get_task_run_err = models.ErrorResponse(detail=f"Failed to get task run '{run_name}'!")
        return obj if isinstance(obj, models.StagedRunSchema) else errs or get_task_run_err
    
    def terminate_task_run(self, run_name: str, **filters) -> models.StagedRunSchema | models.ErrorResponse:
        obj, errs = self._request('PUT', f'task-runs/{run_name}/terminate', params=filters or None, schema=models.StagedRunSchema)
        terminate_task_run_err = models.ErrorResponse(detail=f"Failed to terminate task run '{run_name}'!")
        return obj if isinstance(obj, models.StagedRunSchema) else errs or terminate_task_run_err
    
    def retry_task_run(self, run_name: str, **filters) -> models.StagedRunSchema | models.ErrorResponse:
        obj, errs = self._request('PUT', f'task-runs/{run_name}/retry', params=filters or None, schema=models.StagedRunSchema)
        retry_task_run_err = models.ErrorResponse(detail=f"Failed to retry task run '{run_name}'!")
        return obj if isinstance(obj, models.StagedRunSchema) else errs or retry_task_run_err

    def list_pipelines(self, **filters) -> list[models.PipelineSchema] | models.ErrorResponse:
        obj, errs = self._request('GET', 'pipelines', params=filters or None, schema=models.PipelineSchema)
        list_pipelines_err = models.ErrorResponse(detail="Failed to list pipelines!")
        return obj if isinstance(obj, list) else errs or list_pipelines_err
        
    def get_pipeline(self, pipeline_name: str, **filters) -> models.PipelineSchema | models.ErrorResponse:
        obj, errs = self._request('GET', f'pipelines/{pipeline_name}', params=filters or None, schema=models.PipelineSchema)
        get_pipeline_err = models.ErrorResponse(detail=f"Failed to get pipeline '{pipeline_name}'!")
        return obj if isinstance(obj, models.PipelineSchema) else errs or get_pipeline_err
    
    def submit_pipeline(self, pipeline_name: str, parameters: dict|None=None, **filters) -> models.PipelineSchema | models.ErrorResponse:
        pipeline = self._submit(models.PipelineSchema, pipeline_name, parameters, **filters)
        if isinstance(pipeline, models.PipelineSchema):
            return pipeline
        elif isinstance(pipeline, models.ErrorResponse):
            return pipeline
        else:
            return models.ErrorResponse(detail="Failed to submit pipeline!")
    
    def get_pipeline_run(self, run_name: str, **filters) -> models.StagedRunSchema | models.ErrorResponse:
        obj, errs = self._request('GET', f'pipeline-runs/{run_name}', params=filters or None, schema=models.StagedRunSchema)
        get_pipeline_run_err = models.ErrorResponse(detail=f"Failed to get pipeline run '{run_name}'!")
        return obj if isinstance(obj, models.StagedRunSchema) else errs or get_pipeline_run_err
    
    def terminate_pipeline_run(self, run_name: str, **filters) -> models.StagedRunSchema | models.ErrorResponse:
        obj, errs = self._request('PUT', f'pipeline-runs/{run_name}/terminate', params=filters or None, schema=models.StagedRunSchema)
        terminate_pipeline_run_err = models.ErrorResponse(detail=f"Failed to terminate pipeline run '{run_name}'!")
        return obj if isinstance(obj, models.StagedRunSchema) else errs or terminate_pipeline_run_err
    
    def stop_pipeline_run(self, run_name: str, **filters) -> models.StagedRunSchema | models.ErrorResponse:
        obj, errs = self._request('PUT', f'pipeline-runs/{run_name}/stop', params=filters or None, schema=models.StagedRunSchema)
        stop_pipeline_run_err = models.ErrorResponse(detail=f"Failed to stop pipeline run '{run_name}'!")
        return obj if isinstance(obj, models.StagedRunSchema) else errs or stop_pipeline_run_err
    
    def resume_pipeline_run(self, run_name: str, **filters) -> models.StagedRunSchema | models.ErrorResponse:
        obj, errs = self._request('PUT', f'pipeline-runs/{run_name}/resume', params=filters or None, schema=models.StagedRunSchema)
        resume_pipeline_run_err = models.ErrorResponse(detail=f"Failed to resume pipeline run '{run_name}'!")
        return obj if isinstance(obj, models.StagedRunSchema) else errs or resume_pipeline_run_err
    
    def retry_pipeline_run(self, run_name: str, **filters) -> models.StagedRunSchema | models.ErrorResponse:
        obj, errs = self._request('PUT', f'pipeline-runs/{run_name}/retry', params=filters or None, schema=models.StagedRunSchema)
        retry_pipeline_run_err = models.ErrorResponse(detail=f"Failed to retry pipeline run '{run_name}'!")
        return obj if isinstance(obj, models.StagedRunSchema) else errs or retry_pipeline_run_err
    
    def list_builds(self, **filters) -> list[models.BuildSchema] | models.ErrorResponse:
        obj, errs = self._request('GET', 'builds', params=filters or None, schema=models.BuildSchema)
        list_builds_err = models.ErrorResponse(detail="Failed to list builds!")
        return obj if isinstance(obj, list) else errs or list_builds_err
    
    def get_build(self, build_name: str, **filters) -> models.BuildSchema | models.ErrorResponse:
        obj, errs = self._request('GET', f'builds/{build_name}', params=filters or None, schema=models.BuildSchema)
        get_build_err = models.ErrorResponse(detail=f"Failed to get build '{build_name}'!")
        return obj if isinstance(obj, models.BuildSchema) else errs or get_build_err
    
    def submit_build(self, build_name: str, parameters: dict|None=None,  **filters) -> models.BuildSchema | models.ErrorResponse:
        build = self._submit(models.BuildSchema, build_name, parameters, **filters)
        if isinstance(build, models.BuildSchema):
            return build
        elif isinstance(build, models.ErrorResponse):
            return build
        else:
            return models.ErrorResponse(detail="Failed to submit build!")
    
    def get_build_run(self, run_name: str, **filters) -> models.StagedRunSchema | models.ErrorResponse:
        obj, errs = self._request('GET', f'build-runs/{run_name}', params=filters or None, 
                                  schema=models.StagedRunSchema)
        get_build_run_err = models.ErrorResponse(detail=f"Failed to get build run '{run_name}'!")
        return obj if isinstance(obj, models.StagedRunSchema) else errs or get_build_run_err
    
    def terminate_build_run(self, run_name: str, **filters) -> models.StagedRunSchema | models.ErrorResponse:
        obj, errs = self._request('PUT', f'build-runs/{run_name}/terminate', params=filters or None, 
                                  scheuma=models.StagedRunSchema)
        terminate_build_run_err = models.ErrorResponse(detail=f"Failed to terminate build run '{run_name}'!")
        return obj if isinstance(obj, models.StagedRunSchema) else errs or terminate_build_run_err
    
    def retry_build_run(self, run_name: str, **filters) -> models.StagedRunSchema | models.ErrorResponse:
        obj, errs = self._request('PUT', f'build-runs/{run_name}/retry', params=filters or None, 
                                  schema=models.StagedRunSchema)
        retry_build_run_err = models.ErrorResponse(detail=f"Failed to retry build run '{run_name}'!")
        return obj if isinstance(obj, models.StagedRunSchema) else errs or retry_build_run_err
    
    def list_routes(self, **filters) -> list[models.RouteSchema] | models.ErrorResponse:
        obj, errs = self._request('GET', 'routes', params=filters or None, 
                                  schema=models.RouteSchema)
        list_routes_err = models.ErrorResponse(detail="Failed to list routes!")
        return obj if isinstance(obj, list) else errs or list_routes_err
    
    def get_route(self, route_name: str) -> models.RouteSchema | models.ErrorResponse:
        obj, errs = self._request('GET', f'routes/{route_name}', 
                                  schema=models.RouteSchema)
        get_route_err = models.ErrorResponse(detail=f"Failed to get route '{route_name}'!")
        return obj if isinstance(obj, models.RouteSchema) else errs or get_route_err
    
    def _get_logs(self, 
        run_name: str, 
        lines: int, 
        follow: bool, 
        endpoint: Literal['task-runs', 'pipeline-runs', 'build-runs', 'routes'],
        **filters
    ) -> Iterable[str|models.ErrorResponse]:
        filters['follow'] = follow
        filters['tail'] = lines
        response, errs = self._request('GET', 
            f'{endpoint}/{run_name}/logs', 
            params=filters or None,
            stream=True
        )
        if isinstance(response, requests.Response) and response.ok:
            for line in response.iter_lines():
                yield line
        else:
            yield errs if errs else models.ErrorResponse(detail=response.text)
    
    def get_build_run_logs(self, run_name: str, lines: int, follow: bool, **filters) -> Iterable[str|models.ErrorResponse]:
        yield from self._get_logs(
            run_name=run_name, 
            lines=lines, 
            follow=follow, 
            endpoint='build-runs', 
            **filters
        )

    def get_task_run_logs(self, run_name: str, lines: int, follow: bool, **filters) -> Iterable[str|models.ErrorResponse]:
        yield from self._get_logs(
            run_name=run_name, 
            lines=lines, 
            follow=follow, 
            endpoint='task-runs', 
            **filters
        )

    def get_pipeline_run_logs(self, run_name: str, lines: int, follow: bool, **filters) -> Iterable[str|models.ErrorResponse]:
        yield from self._get_logs(
            run_name=run_name, 
            lines=lines, 
            follow=follow, 
            endpoint='pipeline-runs', 
            **filters
        )
    
    def get_route_logs(self, route_name: str, lines: int, follow: bool, **filters) -> Iterable[str|models.ErrorResponse]:
        yield from self._get_logs(
            run_name=route_name, 
            lines=lines, 
            follow=follow, 
            endpoint='routes', 
            **filters
        )
        
    
    def update_route_thumbnail(self, route_name: str, thumbnail: click.File) -> models.RouteSchema | models.ErrorResponse:
        files = {'thumbnail': thumbnail}
        obj, errs = self._request('POST',f'routes/{route_name}/thumbnail', files=files, schema=models.RouteSchema)
        update_route_thumbnail_err = models.ErrorResponse(detail=f"Failed to update route '{route_name}' thumbnail!")
        return obj if isinstance(obj, models.RouteSchema) else errs or update_route_thumbnail_err
    
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
            obj, errs = self._request('POST','validate', json=spec_dict, schema=models.ProjectSpec)
            err = models.ErrorResponse(detail="Failed to validate project spec!")
            return obj if isinstance(obj, models.ProjectSpec) else errs or err
        
    def allow_project(self, 
        project_name: str, 
        permissions: models.ResourcePermissionsSchema, 
        **filters
    ) -> models.ResourcePermissionsSchema | models.ErrorResponse:
        obj, errs = self._request('POST',
            f'projects/{project_name}/permissions',
            params=filters or None, 
            json=permissions.model_dump()
        )
        allow_project_err = models.ErrorResponse(detail=f"Failed to allow project '{project_name}'!")
        return obj if isinstance(obj, models.ResourcePermissionsSchema) else errs or allow_project_err
    
    def allow_route(self, 
        route_name: str, 
        permissions: models.ResourcePermissionsSchema, 
        **filters
    ) -> models.ResourcePermissionsSchema | models.ErrorResponse:
        obj, errs = self._request('POST',
            f'routes/{route_name}/permissions',
            params=filters or None, 
            json=permissions.model_dump()
        )
        allow_route_err = models.ErrorResponse(detail=f"Failed to allow route '{route_name}'!")
        return obj if isinstance(obj, models.ResourcePermissionsSchema) else errs or allow_route_err