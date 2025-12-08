import tempfile
import os
from io import BytesIO
from unittest.mock import Mock, patch, mock_open

import pytest
from click.testing import CliRunner
from unittest.mock import Mock, patch, ANY
from datetime import datetime, timezone
from requests import Response

from oceanum.cli import main
from oceanum.cli.prax.workflows import (
    list_pipelines, describe_pipeline, submit_pipeline,
    terminate_pipeline, retry_pipeline, get_pipeline_logs
)
from oceanum.cli.prax import models
from oceanum.cli.models import TokenResponse, Auth0Config

timestamp = datetime.now(tz=timezone.utc)

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

        with patch('oceanum.cli.models.TokenResponse.load', return_value=token):
            result = runner.invoke(main, ['prax', 'list', 'pipelines'])
            print(result.output)
            assert result.exit_code == 0

        # With filters
        with patch('oceanum.cli.models.TokenResponse.load', return_value=token):
            result = runner.invoke(main, ['prax', 'list', 'pipelines', '--project=bla'])
            assert result.exit_code == 0
            mock_client.assert_called_with("GET", "pipelines", 
                params={"project": "bla", "stage": None, "org": None, 'search': None, 'user': None},
                schema=models.PipelineSchema
            )

    def test_list_pipelines_error(self, runner, mock_client, error_response):
        # Setup error response
        mock_client.return_value = (error_response, models.ErrorResponse(detail="Not found"))

        with patch('oceanum.cli.models.TokenResponse.load', return_value=token):

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
                "parent": 'pipeline-123',
                "created_at": timestamp,
                "updated_at": timestamp,
                "status": "running",
                "runs": []
            }
        })
        mock_client.return_value = (mock_response, None)

        with patch('oceanum.cli.models.TokenResponse.load', return_value=token):
            result = runner.invoke(main, ['prax', 'submit', 'pipeline', 'test-pipeline'])
            assert result.exit_code == 0
            assert "Pipeline submitted successfully" in result.output
        # with filters and parameters
        with patch('oceanum.cli.models.TokenResponse.load', return_value=token):
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
            "parent": 'pipeline-123',
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
            "parent": 'pipeline-123',
            "created_at": timestamp,
            "updated_at": timestamp,
            "status": "failed",
        })
        mock_client.return_value = (mock_response, None)

        result = runner.invoke(main, ['prax', 'retry', 'pipeline', 'test-pipeline'])
        assert result.exit_code == 0
        assert "Pipeline retried successfully" in result.output

    def test_delete_pipeline_run_success(self, runner, mock_client, mock_response):
        mock_client.return_value = ("Pipeline run deleted successfully!", None)
        with patch('oceanum.cli.prax.client.PRAXClient.get_pipeline_run', 
            return_value=models.StagedRunSchema(
                id="run-123",
                name="test-pipeline",
                project="test-project",
                parent= 'pipeline-123',
                stage="dev",
                org="test-org",
                created_at=timestamp,
                updated_at=timestamp,
                status="succeeded",
        )):
            with patch('oceanum.cli.models.TokenResponse.load', return_value=token):
                result = runner.invoke(main, ['prax', 'delete', 'pipeline', 'test-pipeline'])
                assert result.exit_code == 0
                assert "deleted successfully" in result.output
                mock_client.assert_called_with("DELETE", "pipeline-runs/test-pipeline", 
                    params={"project": None, "org": None, "user": None, "stage": None}
                )

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
                "parent": 'pipeline-123',
                "created_at": timestamp,
                "updated_at": timestamp,
                "status": "running",
            }
        })
        #mock_response.content.return_value = ["Log line 1", "Log line 2"]
        mock_response.iter_lines.return_value = iter(["Log line 1", "Log line 2"])

        with patch('oceanum.cli.models.TokenResponse.load', return_value=token):
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
                "parent": 'pipeline-123',
                "project": "test-project",
                "stage": "dev",
                "org": "test-org",
                "created_at": timestamp,
                "updated_at": timestamp,
                "status": "running",
            }
        })
        mock_response.iter_lines.return_value = iter(["Log line 1", "Log line 2"])

        with patch('oceanum.cli.models.TokenResponse.load', return_value=token):
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

        with patch('oceanum.cli.models.TokenResponse.load', return_value=token):
            result = runner.invoke(main, ['prax', 'list', 'tasks'])
            assert result.exit_code == 0

        with patch('oceanum.cli.models.TokenResponse.load', return_value=token):
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

        with patch('oceanum.cli.models.TokenResponse.load', return_value=token):
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
                "parent": 'task-123',
                "org": "test-org",
                "created_at": timestamp,
                "updated_at": timestamp,
                "status": "running",
            }
        })
        mock_client.return_value = (mock_response, None)

        with patch('oceanum.cli.models.TokenResponse.load', return_value=token):
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
                "parent": 'task-123',
                "org": "test-org",
                "created_at": timestamp,
                "updated_at": timestamp,
                "status": "running",
            }
        })
        mock_response.iter_lines.return_value = iter(["Log line 1", "Log line 2"])

        with patch('oceanum.cli.models.TokenResponse.load', return_value=token):
            with patch('oceanum.cli.prax.client.PRAXClient.get_task') as mock_get_task:
                mock_get_task.return_value = task_response
                result = runner.invoke(main, ['prax', 'logs', 'task', 'test-task'])
                assert result.exit_code == 0
                assert "Log line 1" in result.output

    def test_delete_task_run_success(self, runner, mock_client, mock_response):
        mock_client.return_value = ("Task run deleted successfully!", None)
        with patch('oceanum.cli.prax.client.PRAXClient.get_task_run', 
                   return_value=models.StagedRunSchema(
            id="run-123",
            name="test-task",
            project="test-project",
            stage="dev",
            org="test-org",
            parent= 'task-123',
            created_at=timestamp,
            updated_at=timestamp,
            status="succeeded",
        )):
            with patch('oceanum.cli.models.TokenResponse.load', return_value=token):
                result = runner.invoke(main, ['prax', 'delete', 'task', 'test-task'])
                assert result.exit_code == 0
                assert "deleted successfully" in result.output
                mock_client.assert_called_with("DELETE", "task-runs/test-task", 
                    params={"project": None, "org": None, "user": None, "stage": None}
                )

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

        with patch('oceanum.cli.models.TokenResponse.load', return_value=token):
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

        with patch('oceanum.cli.models.TokenResponse.load', return_value=token):
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
                "parent": 'build-123',
                "created_at": timestamp,
                "updated_at": timestamp,
                "status": "running",
            }
        })
        mock_client.return_value = (mock_response, None)

        with patch('oceanum.cli.models.TokenResponse.load', return_value=token):
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
                "parent": 'build-123',
                "org": "test-org",
                "created_at": timestamp,
                "updated_at": timestamp,
                "status": "running",
            }
        })
        mock_response.iter_lines.return_value = iter(["Log line 1", "Log line 2"])

        with patch('oceanum.cli.models.TokenResponse.load', return_value=token):
            with patch('oceanum.cli.prax.client.PRAXClient.get_build') as mock_get_build:
                mock_get_build.return_value = build_response
                result = runner.invoke(main, ['prax', 'logs', 'build', 'test-build'])
                assert result.exit_code == 0
                assert "Log line 1" in result.output


    def test_delete_build_run_success(self, runner, mock_client, mock_response):
        mock_client.return_value = ("Build run deleted successfully!", None)
        with patch('oceanum.cli.prax.client.PRAXClient.get_build_run', return_value=models.StagedRunSchema(
            id="run-123",
            name="test-build",
            project="test-project",
            stage="dev",
            org="test-org",
            created_at=timestamp,
            updated_at=timestamp,
            parent= 'build-123',
            status="succeeded",
        )):
            with patch('oceanum.cli.models.TokenResponse.load', return_value=token):
                result = runner.invoke(main, ['prax', 'delete', 'build', 'test-build'])
                print(result.output)
                assert result.exit_code == 0
                assert "deleted successfully" in result.output
                mock_client.assert_called_with("DELETE", "build-runs/test-build", 
                    params={"project": None, "org": None, "user": None, "stage": None}
                )


# Add these test classes to your existing test file

class TestDownloadCommands:
    def test_download_task_artifact_success(self, runner, mock_client, mock_response):
        # Mock the get_task_run preflight check
        mock_task_run = models.StagedRunSchema(
            id="test-task-run-123",
            org="test-org",
            project="test-project",
            stage="dev",
            name="test-task-run-123",
            parent= 'task-123',
            status="Succeeded",
            created_at=timestamp,
            updated_at=timestamp,
            message="Completed successfully"
        )
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, 'test_artifact.gz')
            
            with patch('oceanum.cli.models.TokenResponse.load', return_value=token):
                with patch('oceanum.cli.prax.workflows.PRAXClient') as mock_prax_client:
                    client_instance = Mock()
                    client_instance.get_task_run.return_value = mock_task_run
                    client_instance.download_task_run_artifact.return_value = True
                    mock_prax_client.return_value = client_instance
                    
                    result = runner.invoke(main, [
                        'prax', 'download', 'task-artifact', 'test-task-run-123',
                        '--artifact-name', 'test-artifact',
                        '--output', output_path
                    ])
                    print(result.output)
                    assert result.exit_code == 0
                    assert "Artifact 'test-artifact' downloaded successfully!" in result.output
                    
                    # Verify the client calls
                    client_instance.get_task_run.assert_called_once_with("test-task-run-123")
                    client_instance.download_task_run_artifact.assert_called_once_with(
                        "test-task-run-123", "test-artifact", output_path
                    )

    def test_download_task_artifact_default_path(self, runner, mock_client, mock_response):
        mock_task_run = models.StagedRunSchema(
            id="test-task-run-123",
            org="test-org",
            project="test-project",
            stage="dev",
            parent= 'task-123',
            name="test-task-run-123",
            status="Succeeded",
            created_at=timestamp,
            updated_at=timestamp,
            message="Completed successfully"
        )
        
        with patch('oceanum.cli.models.TokenResponse.load', return_value=token):
            with patch('oceanum.cli.prax.workflows.PRAXClient') as mock_prax_client:
                client_instance = Mock()
                client_instance.get_task_run.return_value = mock_task_run
                client_instance.download_task_run_artifact.return_value = True
                mock_prax_client.return_value = client_instance
                
                result = runner.invoke(main, [
                    'prax', 'download', 'task-artifact', 'test-task-run',
                    '--artifact-name', 'test-artifact'
                ])
                
                assert result.exit_code == 0
                # Should use None for output path (default behavior)
                client_instance.download_task_run_artifact.assert_called_once_with(
                    "test-task-run-123", "test-artifact", None
                )

    def test_download_task_artifact_task_not_found(self, runner, mock_client):
        error_response = models.ErrorResponse(detail="Task run not found!")
        
        with patch('oceanum.cli.models.TokenResponse.load', return_value=token):
            with patch('oceanum.cli.prax.workflows.PRAXClient') as mock_prax_client:
                client_instance = Mock()
                client_instance.get_task_run.return_value = error_response
                mock_prax_client.return_value = client_instance
                
                result = runner.invoke(main, [
                    'prax', 'download', 'task-artifact', 'nonexistent-task',
                    '--artifact-name', 'test-artifact'
                ])
                
                assert result.exit_code == 1
                assert "Error fetching task run:" in result.output

    def test_download_task_artifact_download_failed(self, runner, mock_client):
        mock_task_run = models.StagedRunSchema(
            id="test-task-run-123",
            org="test-org",
            project="test-project",
            stage="dev",
            name="test-task-run-123",
            parent= 'task-123',
            status="Succeeded",
            created_at=timestamp,
            updated_at=timestamp,
            message="Completed successfully"
        )
        
        with patch('oceanum.cli.models.TokenResponse.load', return_value=token):
            with patch('oceanum.cli.prax.workflows.PRAXClient') as mock_prax_client:
                client_instance = Mock()
                client_instance.get_task_run.return_value = mock_task_run
                client_instance.download_task_run_artifact.return_value = False
                mock_prax_client.return_value = client_instance
                
                result = runner.invoke(main, [
                    'prax', 'download', 'task-artifact', 'test-task-run',
                    '--artifact-name', 'test-artifact'
                ])
                
                # Should not print success message if download returns False
                assert "Artifact 'test-artifact' downloaded successfully!" not in result.output

    def test_download_pipeline_artifact_success(self, runner, mock_client, mock_response):
        mock_pipeline_run = models.StagedRunSchema(
            id="test-pipeline-run-456",
            org="test-org",
            project="test-project",
            stage="dev",
            parent= 'pipeline-123',
            name="test-pipeline-run-456",
            status="Succeeded",
            created_at=timestamp,
            updated_at=timestamp,
            message="Pipeline completed successfully"
        )
        
        with patch('oceanum.cli.models.TokenResponse.load', return_value=token):
            with patch('oceanum.cli.prax.workflows.PRAXClient') as mock_prax_client:
                client_instance = Mock()
                client_instance.get_pipeline_run.return_value = mock_pipeline_run
                client_instance.download_pipeline_run_artifact.return_value = True
                mock_prax_client.return_value = client_instance
                
                result = runner.invoke(main, [
                    'prax', 'download', 'pipeline-artifact', 'test-pipeline-run',
                    '--artifact-name', 'test-artifact',
                    '--step-name', 'test-step',
                    '--output', '/tmp/pipeline_artifact.gz'
                ])
                
                assert result.exit_code == 0
                assert "Artifact 'test-artifact' from step 'test-step' downloaded successfully!" in result.output
                
                # Verify the client calls
                client_instance.get_pipeline_run.assert_called_once_with(
                    "test-pipeline-run", 
                    org=None, user=None, project=None, stage=None
                )
                client_instance.download_pipeline_run_artifact.assert_called_once_with(
                    "test-pipeline-run-456", "test-artifact", "test-step", "/tmp/pipeline_artifact.gz"
                )

    def test_download_pipeline_artifact_missing_step_name(self, runner, mock_client):
        with patch('oceanum.cli.models.TokenResponse.load', return_value=token):
            result = runner.invoke(main, [
                'prax', 'download', 'pipeline-artifact', 'test-pipeline-run',
                '--artifact-name', 'test-artifact'
                # Missing --step-name
            ])
            
            # Should fail due to missing required step-name argument
            assert result.exit_code != 0
            assert "Missing option" in result.output or "Error" in result.output

    def test_download_pipeline_artifact_from_pipeline_schema(self, runner, mock_client):
        """Test when we get pipeline from get_pipeline instead of get_pipeline_run"""
        mock_pipeline_run = models.StagedRunSchema(
            id="test-pipeline-run-456",
            org="test-org",
            project="test-project",
            parent= 'pipeline-123',
            stage="dev",
            name="test-pipeline-run-456",
            status="Succeeded",
            created_at=timestamp,
            updated_at=timestamp,
            message="Pipeline completed successfully"
        )
        
        mock_pipeline = models.PipelineSchema(
            id="pipeline-123",
            name="test-pipeline",
            project="test-project",
            stage="dev",
            org="test-org",
            created_at=timestamp,
            updated_at=timestamp,
            last_run=mock_pipeline_run
        )
        
        with patch('oceanum.cli.models.TokenResponse.load', return_value=token):
            with patch('oceanum.cli.prax.workflows.PRAXClient') as mock_prax_client:
                client_instance = Mock()
                client_instance.get_pipeline.return_value = mock_pipeline
                client_instance.download_pipeline_run_artifact.return_value = True
                mock_prax_client.return_value = client_instance
                
                result = runner.invoke(main, [
                    'prax', 'download', 'pipeline-artifact', 'test-pipeline',
                    '--artifact-name', 'test-artifact',
                    '--step-name', 'test-step'
                ])
                
                assert result.exit_code == 0
                
                # Should use the last_run from the pipeline schema
                client_instance.download_pipeline_run_artifact.assert_called_once_with(
                    "test-pipeline-run-456", "test-artifact", "test-step", None
                )

    def test_download_pipeline_artifact_no_run_found(self, runner, mock_client):
        """Test when pipeline has no last_run and get_pipeline_run returns None"""
        mock_pipeline = models.PipelineSchema(
            id="pipeline-123",
            name="test-pipeline",
            project="test-project",
            stage="dev",
            org="test-org",
            created_at=timestamp,
            updated_at=timestamp,
            last_run=None
        )
        
        with patch('oceanum.cli.models.TokenResponse.load', return_value=token):
            with patch('oceanum.cli.prax.workflows.PRAXClient') as mock_prax_client:
                client_instance = Mock()
                client_instance.get_pipeline.return_value = mock_pipeline
                client_instance.get_pipeline_run.return_value = None
                mock_prax_client.return_value = client_instance
                
                result = runner.invoke(main, [
                    'prax', 'download', 'pipeline-artifact', 'test-pipeline',
                    '--artifact-name', 'test-artifact',
                    '--step-name', 'test-step'
                ])
                
                assert result.exit_code == 1
                assert "No pipeline run found for pipeline: test-pipeline" in result.output