import click
import pytest
from click.testing import CliRunner
from unittest.mock import Mock, patch, ANY
from datetime import datetime
from requests import Response

from oceanum.cli.main import main
from oceanum.cli.prax.workflows import (
    list_pipelines, describe_pipeline, submit_pipeline,
    terminate_pipeline, retry_pipeline, get_pipeline_logs
)
from oceanum.cli.prax import models
from oceanum.cli.common.models import TokenResponse, Auth0Config

timestamp = datetime.now().isoformat()

@pytest.fixture
def mock_response():
    response = Mock(spec=Response)
    response.ok = True
    return response

@pytest.fixture
def mock_client(mock_response):
    with patch('oceanum.cli.prax.client.PRAXClient._request') as mock:
        # Configure mock to return (response, None) for success case
        mock_response.json.return_value = {}  # default empty response
        mock.return_value = (mock_response, None)
        yield mock

@pytest.fixture
def runner():
    return CliRunner()

@pytest.fixture
def error_response():
    response = Mock(spec=Response)
    response.ok = False
    response.status_code = 404
    response.json.return_value = {
        "status_code": 404,
        "detail": "Not found"
    }
    return response

token = TokenResponse(
    access_token="test_token",
    token_type="Bearer",
    refresh_token="test_refresh_token",
    expires_in=86400
)

class TestPipelineCommands:
    def test_list_pipelines_success(self, runner, mock_client, mock_response):
        # Setup mock response
        mock_response = [
            models.PipelineSchema(**{
                "id": "pipeline-123",
                "name": "test-pipeline",
                "project": "test-project",
                "stage": "dev",
                "org": "test-org",
                "created_at": timestamp,
                "updated_at": timestamp,
                "last_run": None
            })
        ]
        mock_client.return_value = (mock_response, None)

        with patch('oceanum.cli.common.models.TokenResponse.load', return_value=token):
            result = runner.invoke(main, ['prax', 'list', 'pipelines'])
            print(result.output)
            assert result.exit_code == 0

        # With filters
        with patch('oceanum.cli.common.models.TokenResponse.load', return_value=token):
            result = runner.invoke(main, ['prax', 'list', 'pipelines', '--project=bla'])
            assert result.exit_code == 0
            mock_client.assert_called_with("GET", "pipelines", 
                params={"project": "bla", "stage": None, "org": None, 'search': None, 'user': None},
                schema=models.PipelineSchema
            )

    def test_list_pipelines_error(self, runner, mock_client, error_response):
        # Setup error response
        mock_client.return_value = (error_response, models.ErrorResponse(detail="Not found"))

        with patch('oceanum.cli.common.models.TokenResponse.load', return_value=token):

            result = runner.invoke(main, ['prax', 'list', 'pipelines'])
            assert result.exit_code == 1
            assert "Not found" in result.output

    def test_describe_pipeline_success(self, runner, mock_client, mock_response):
        mock_response = models.PipelineSchema(**{
            "id": "pipeline-123",
            "name": "test-pipeline",
            "project": "test-project",
            "stage": "dev",
            "org": "test-org",
            "created_at": timestamp,
            "updated_at": timestamp,
            "last_run": None
        })
        mock_client.return_value = (mock_response, None)

        result = runner.invoke(main, ['prax', 'describe', 'pipeline', 'test-pipeline'])
        assert result.exit_code == 0
        mock_client.assert_called_with("GET", "pipelines/test-pipeline", 
            params={"org": None, 'user': None, 'project': None, 'stage': None},
            schema=models.PipelineSchema
        )

        # Test with filters
        result = runner.invoke(main, ['prax', 'describe', 'pipeline', 'test-pipeline','--project=bla'])
        assert result.exit_code == 0
        mock_client.assert_called_with("GET", "pipelines/test-pipeline", 
            params={"org": None, 'user': None, 'project': 'bla', 'stage': None},
            schema=models.PipelineSchema
        )

    def test_submit_pipeline_success(self, runner, mock_client, mock_response):
        mock_response = models.PipelineSchema(**{
            "id": "pipeline-123",
            "name": "test-pipeline",
            "project": "test-project",
            "stage": "dev",
            "org": "test-org",
            "created_at": timestamp,
            "updated_at": timestamp,
            "last_run": {
                "id": "run-123",
                "name": "run-123",
                "project": "test-project",
                "stage": "dev",
                "org": "test-org",
                "created_at": timestamp,
                "updated_at": timestamp,
                "status": "running",
                "runs": []
            }
        })
        mock_client.return_value = (mock_response, None)

        with patch('oceanum.cli.common.models.TokenResponse.load', return_value=token):
            result = runner.invoke(main, ['prax', 'submit', 'pipeline', 'test-pipeline'])
            assert result.exit_code == 0
            assert "Pipeline submitted successfully" in result.output
        # with filters and parameters
        with patch('oceanum.cli.common.models.TokenResponse.load', return_value=token):
            result = runner.invoke(main, ['prax', 'submit', 'pipeline', 'test-pipeline', '--project', 'bla', '-p', 'key=val'])
            assert result.exit_code == 0
            assert "Pipeline submitted successfully" in result.output
            mock_client.assert_called_with("POST", "pipelines/test-pipeline/submit", 
                json={"parameters": {"key": "val"}},
                params={"project": "bla", "org": None, "user": None, "stage": None},
                schema=models.PipelineSchema
            )



    def test_terminate_pipeline_success(self, runner, mock_client, mock_response):
        mock_response = models.StagedRunSchema(**{
            "id": "pipeline-123",
            "name": "test-pipeline",
            "object_ref": models.ObjectRef(root="pipeline-123"),
            "project": "test-project",
            "stage": "dev",
            "org": "test-org",
            "created_at": timestamp,
            "updated_at": timestamp,
            "status": "running",
        })
        mock_client.return_value = (mock_response, None)
        result = runner.invoke(main, ['prax', 'terminate', 'pipeline', 'test-pipeline'])
        print(result.output)
        assert result.exit_code == 0
        assert "Pipeline terminated successfully" in result.output

    def test_retry_pipeline_success(self, runner, mock_client, mock_response):
        mock_response = models.StagedRunSchema(**{
            "id": "pipeline-123",
            "name": "test-pipeline",
            "project": "test-project",
            "object_ref": models.ObjectRef(root="pipeline-123"),
            "stage": "dev",
            "org": "test-org",
            "created_at": timestamp,
            "updated_at": timestamp,
            "status": "failed",
        })
        mock_client.return_value = (mock_response, None)

        result = runner.invoke(main, ['prax', 'retry', 'pipeline', 'test-pipeline'])
        assert result.exit_code == 0
        assert "Pipeline retried successfully" in result.output

    def test_get_pipeline_logs(self, runner, mock_client, mock_response):
        pipeline_get_response = models.PipelineSchema(**{
            "id": "pipeline-123",
            "name": "test-pipeline",
            "project": "test-project",
            "stage": "dev",
            "org": "test-org",
            "created_at": timestamp,
            "updated_at": timestamp,
            "last_run": {
                "id": "run-123",
                "name": "run-123",
                "project": "test-project",
                "stage": "dev",
                "org": "test-org",
                "created_at": timestamp,
                "updated_at": timestamp,
                "status": "running",
                "runs": []
            }
        })
        #mock_response.content.return_value = ["Log line 1", "Log line 2"]
        mock_response.iter_lines.return_value = iter(["Log line 1", "Log line 2"])

        with patch('oceanum.cli.common.models.TokenResponse.load', return_value=token):
            with patch('oceanum.cli.prax.client.PRAXClient.get_pipeline') as mock_get_pipeline:
                mock_get_pipeline.return_value =  pipeline_get_response
                result = runner.invoke(main, ['prax', 'logs', 'pipeline', 'test-pipeline'])
                assert result.exit_code == 0
                assert "Log line 1" in result.output
                assert "Log line 2" in result.output

    def test_get_pipeline_logs_with_options(self, runner, mock_client, mock_response):
        # Mock the response for the pipeline
        pipeline_get_response = models.PipelineSchema(**{
            "id": "pipeline-123",
            "name": "test-pipeline",
            "project": "test-project",
            "stage": "dev",
            "org": "test-org",
            "created_at": timestamp,
            "updated_at": timestamp,
            "last_run": {
                "id": "run-123",
                "name": "run-123",
                "project": "test-project",
                "stage": "dev",
                "org": "test-org",
                "created_at": timestamp,
                "updated_at": timestamp,
                "status": "running",
                "runs": []
            }
        })
        mock_response.iter_lines.return_value = iter(["Log line 1", "Log line 2"])

        with patch('oceanum.cli.common.models.TokenResponse.load', return_value=token):
            with patch('oceanum.cli.prax.client.PRAXClient.get_pipeline') as mock_get_pipeline:
                mock_get_pipeline.return_value =  pipeline_get_response
                result = runner.invoke(main, ['prax', 'logs', 'pipeline', 'test-pipeline', '--follow'])
                assert result.exit_code == 0
                assert "Log line 1" in result.output

class TestTaskCommands:
    def test_list_tasks_success(self, runner, mock_client, mock_response):
        mock_response = [
            models.TaskSchema(**{
                "id": "task-123",
                "name": "test-task",
                "project": "test-project",
                "stage": "dev",
                "org": "test-org",
                "created_at": timestamp,
                "updated_at": timestamp,
                "last_run": None
            })
        ]
        mock_client.return_value = (mock_response, None)

        with patch('oceanum.cli.common.models.TokenResponse.load', return_value=token):
            result = runner.invoke(main, ['prax', 'list', 'tasks'])
            assert result.exit_code == 0

        with patch('oceanum.cli.common.models.TokenResponse.load', return_value=token):
            result = runner.invoke(main, ['prax', 'list', 'tasks', '--project=bla'])
            assert result.exit_code == 0
            mock_client.assert_called_with("GET", "tasks", 
                params={"project": "bla", "stage": None, "org": None, 'search': None, 'user': None},
                schema=models.TaskSchema
            )

    def test_describe_task_success(self, runner, mock_client, mock_response):
        mock_response = models.TaskSchema(**{
            "id": "task-123",
            "name": "test-task",
            "project": "test-project",
            "stage": "dev",
            "org": "test-org",
            "created_at": timestamp,
            "updated_at": timestamp,
            "last_run": None
        })
        mock_client.return_value = (mock_response, None)

        with patch('oceanum.cli.common.models.TokenResponse.load', return_value=token):
            result = runner.invoke(main, ['prax', 'describe', 'task', 'test-task'])
            assert result.exit_code == 0

    def test_submit_task_success(self, runner, mock_client, mock_response):
        mock_response = models.TaskSchema(**{
            "id": "task-123",
            "name": "test-task",
            "project": "test-project",
            "stage": "dev",
            "org": "test-org",
            "created_at": timestamp,
            "updated_at": timestamp,
            "last_run": {
                "id": "run-123",
                "name": "run-123",
                "project": "test-project",
                "stage": "dev",
                "org": "test-org",
                "created_at": timestamp,
                "updated_at": timestamp,
                "status": "running",
                "runs": []
            }
        })
        mock_client.return_value = (mock_response, None)

        with patch('oceanum.cli.common.models.TokenResponse.load', return_value=token):
            result = runner.invoke(main, ['prax', 'submit', 'task', 'test-task', '-p', 'key=val'])
            assert result.exit_code == 0
            assert "Task submitted successfully" in result.output
            mock_client.assert_called_with("POST", "tasks/test-task/submit", 
                json={"parameters": {"key": "val"}},
                params={"project": None, "org": None, "user": None, "stage": None},
                schema=models.TaskSchema
            )

    def test_get_task_logs(self, runner, mock_client, mock_response):
        task_response = models.TaskSchema(**{
            "id": "task-123",
            "name": "test-task",
            "project": "test-project",
            "stage": "dev",
            "org": "test-org",
            "created_at": timestamp,
            "updated_at": timestamp,
            "last_run": {
                "id": "run-123",
                "name": "run-123",
                "project": "test-project",
                "stage": "dev",
                "org": "test-org",
                "created_at": timestamp,
                "updated_at": timestamp,
                "status": "running",
                "runs": []
            }
        })
        mock_response.iter_lines.return_value = iter(["Log line 1", "Log line 2"])

        with patch('oceanum.cli.common.models.TokenResponse.load', return_value=token):
            with patch('oceanum.cli.prax.client.PRAXClient.get_task') as mock_get_task:
                mock_get_task.return_value = task_response
                result = runner.invoke(main, ['prax', 'logs', 'task', 'test-task'])
                assert result.exit_code == 0
                assert "Log line 1" in result.output

class TestBuildCommands:
    def test_list_builds_success(self, runner, mock_client, mock_response):
        mock_response = [
            models.BuildSchema(**{
                "id": "build-123",
                "name": "test-build",
                "project": "test-project",
                "stage": "dev",
                "org": "test-org",
                "created_at": timestamp,
                "updated_at": timestamp,
                "source_ref": "main",
                "last_run": None
            })
        ]
        mock_client.return_value = (mock_response, None)

        with patch('oceanum.cli.common.models.TokenResponse.load', return_value=token):
            result = runner.invoke(main, ['prax', 'list', 'builds'])
            assert result.exit_code == 0

    def test_describe_build_success(self, runner, mock_client, mock_response):
        mock_response = models.BuildSchema(**{
            "id": "build-123",
            "name": "test-build",
            "project": "test-project",
            "stage": "dev",
            "org": "test-org",
            "created_at": timestamp,
            "updated_at": timestamp,
            "source_ref": "main",
            "commit_sha": "abc123",
            "last_run": None
        })
        mock_client.return_value = (mock_response, None)

        with patch('oceanum.cli.common.models.TokenResponse.load', return_value=token):
            result = runner.invoke(main, ['prax', 'describe', 'build', 'test-build'])
            assert result.exit_code == 0

    def test_submit_build_success(self, runner, mock_client, mock_response):
        mock_response = models.BuildSchema(**{
            "id": "build-123",
            "name": "test-build",
            "project": "test-project",
            "stage": "dev",
            "org": "test-org",
            "created_at": timestamp,
            "updated_at": timestamp,
            "source_ref": "main",
            "last_run": {
                "id": "run-123",
                "name": "run-123",
                "project": "test-project",
                "stage": "dev",
                "org": "test-org",
                "created_at": timestamp,
                "updated_at": timestamp,
                "status": "running",
                "runs": []
            }
        })
        mock_client.return_value = (mock_response, None)

        with patch('oceanum.cli.common.models.TokenResponse.load', return_value=token):
            result = runner.invoke(main, ['prax', 'submit', 'build', 'test-build'])
            assert result.exit_code == 0
            assert "Build submitted successfully" in result.output

    def test_get_build_logs(self, runner, mock_client, mock_response):
        build_response = models.BuildSchema(**{
            "id": "build-123",
            "name": "test-build",
            "project": "test-project",
            "stage": "dev",
            "org": "test-org",
            "created_at": timestamp,
            "updated_at": timestamp,
            "source_ref": "main",
            "last_run": {
                "id": "run-123",
                "name": "run-123",
                "project": "test-project",
                "stage": "dev",
                "org": "test-org",
                "created_at": timestamp,
                "updated_at": timestamp,
                "status": "running",
                "runs": []
            }
        })
        mock_response.iter_lines.return_value = iter(["Log line 1", "Log line 2"])

        with patch('oceanum.cli.common.models.TokenResponse.load', return_value=token):
            with patch('oceanum.cli.prax.client.PRAXClient.get_build') as mock_get_build:
                mock_get_build.return_value = build_response
                result = runner.invoke(main, ['prax', 'logs', 'build', 'test-build'])
                assert result.exit_code == 0
                assert "Log line 1" in result.output



