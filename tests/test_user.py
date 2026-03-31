from unittest import TestCase
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from oceanum.cli import main
from oceanum.cli.prax import client, models

runner = CliRunner()


class TestUser(TestCase):
    def test_get_org_usage(self):
        response = MagicMock(status_code=200)
        response.ok = True
        response.json.return_value = {
            "time_series": {
                "cpu_limits": [
                    {"timestamp": "2023-01-01T10:00:00Z", "value": 1.5},
                    {"timestamp": "2023-01-01T10:05:00Z", "value": 2.0},
                ],
                "memory_limits": [],
            },
            "billing_totals": {
                "cpu": 123,
                "memory": 456,
                "ephemeral_storage": 0,
                "persistent_storage": 0,
                "gpu": 0,
            },
            "metadata": {
                "org": "test-org",
                "project_name": "test-project",
                "start_time": "2023-01-01T10:00:00Z",
                "end_time": "2023-01-01T12:00:00Z",
                "step": "5m",
                "duration_seconds": 7200,
                "data_points": 2,
            },
        }
        with patch.object(
            client.PRAXClient, "get_org_usage", return_value=response.json.return_value
        ) as mock_get_org_usage:
            result = runner.invoke(
                main,
                [
                    "prax",
                    "usage",
                    "org",
                    "test-org",
                    "--project-name",
                    "test-project",
                    "--start",
                    "2023-01-01T10:00:00Z",
                    "--end",
                    "2023-01-01T12:00:00Z",
                    "--step",
                    "5m",
                ],
            )
            assert result.exit_code == 0
            assert "Usage" in result.output
            assert "Coverage:" in result.output
            assert "Resolution: 5m  Samples: 2" in result.output
            assert "2023-01-01 10:00 UTC -> 2023-01-01 12:00 UTC" in result.output
            assert "Summary" in result.output
            assert "Billing Totals" in result.output
            assert "Cpu Limits" in result.output
            assert "avg 1.75 cores" in result.output
            assert "peak 2.00 cores" in result.output
            assert "0.03 core-hours" in result.output
            assert "0.00 GiB-hours" in result.output
            assert "current 2.00 cores" in result.output
            mock_get_org_usage.assert_called_with(
                "test-org",
                project_name="test-project",
                start="2023-01-01T10:00:00Z",
                end="2023-01-01T12:00:00Z",
                step="5m",
            )

    def test_get_org_usage_yaml_output(self):
        response = MagicMock(status_code=200)
        response.ok = True
        response.json.return_value = {
            "time_series": {"cpu_limits": []},
            "billing_totals": {"cpu": 123},
            "metadata": {"org": "test-org", "project_name": None, "step": "1h"},
        }
        with patch.object(
            client.PRAXClient, "get_org_usage", return_value=response.json.return_value
        ):
            result = runner.invoke(
                main,
                ["prax", "usage", "org", "test-org", "--output", "yaml"],
            )
            assert result.exit_code == 0
            assert "billing_totals:" in result.output

    def test_create_user_secret_help(self):
        result = runner.invoke(main, ["prax", "create", "user-secret", "--help"])
        assert result.exit_code == 0

    def test_create_user_secret(self):
        user_get_response = [
            models.UserSchema(
                **{
                    "username": "test-user",
                    "email": "test-user@test.com",
                    "token": "test-token",
                    "deployable_orgs": ["test-org"],
                    "admin_orgs": ["test-org"],
                    "current_org": {
                        "name": "test-org",
                        "projects": ["test-project"],
                        "tier": {
                            "name": "test-tier",
                        },
                        "usage": {
                            "name": "usage",
                        },
                        "resources": [],
                    },
                    "projects": [],
                }
            )
        ]
        create_response = models.SecretSpec(
            name="test-secret",
            description="test-secret",
            data=models.SecretData(root={"key": models.SecretStr("value")}),
        )

        with patch.object(client.PRAXClient, "get_users") as get_users_mock:
            get_users_mock.return_value = user_get_response
            with patch.object(client.PRAXClient, "_request") as mock_request:
                mock_request.return_value = (create_response, None)
                result = runner.invoke(
                    main,
                    [
                        "prax",
                        "create",
                        "user-secret",
                        "test-secret",
                        "--data",
                        "key=value",
                    ],
                )
                print(result.exc_info)
                assert "test-secret" in result.output

    def test_describe_user(self):
        response = [
            models.UserSchema(
                **{
                    "id": "test-user-id",
                    "username": "test-user",
                    "email": "test-user@test.com",
                    "token": "test-token",
                    "all_orgs": ["test-org"],
                    "deployable_orgs": ["test-org"],
                    "admin_orgs": ["test-org"],
                    "projects": ["test-project"],
                    "current_org": {
                        "name": "test-org",
                        "projects": ["test-project"],
                        "tier": {
                            "max_cpu": 32000,
                            "max_cpu_per_service": 4000,
                            "max_cpu_per_task": 32000,
                            "max_memory_per_service": 32000,
                            "max_memory_per_task": 32000,
                            "max_memory": 128000,
                            "max_gpu": 0,
                            "max_ephemeral_storage": 100000,
                            "max_ephemeral_storage_per_service": 50000,
                            "max_ephemeral_storage_per_task": 50000,
                            "max_concurrent_workflows": 0,
                            "max_persistent_storage": 100000,
                            "max_persistent_volume_size": 10000,
                            "max_persistent_volumes": 10,
                            "max_projects": 50,
                            "max_stages": 100,
                            "max_builds": 100,
                            "max_pipelines": 100,
                            "max_tasks": 100,
                            "max_secrets": 100,
                            "max_images": 100,
                            "max_sources": 100,
                            "max_notebooks": 10,
                            "max_services": 10,
                            "max_configmaps": 100,
                            "name": "basic",
                        },
                        "usage": {
                            "max_cpu": 0,
                            "max_cpu_per_service": 0,
                            "max_cpu_per_task": 0,
                            "max_memory_per_service": 0,
                            "max_memory_per_task": 0,
                            "max_memory": 0,
                            "max_gpu": 0,
                            "max_ephemeral_storage": 0,
                            "max_ephemeral_storage_per_service": 0,
                            "max_ephemeral_storage_per_task": 0,
                            "max_concurrent_workflows": 0,
                            "max_persistent_storage": 0,
                            "max_persistent_volume_size": 0,
                            "max_persistent_volumes": 0,
                            "max_projects": 0,
                            "max_stages": 0,
                            "max_builds": 0,
                            "max_pipelines": 0,
                            "max_tasks": 0,
                            "max_secrets": 0,
                            "max_images": 0,
                            "max_sources": 0,
                            "max_notebooks": 0,
                            "max_services": 0,
                            "max_configmaps": 0,
                            "name": "usage",
                        },
                        "resources": [
                            {
                                "org": "test-org",
                                "name": "test-secret",
                                "created_at": "2021-09-09T12:00:00Z",
                                "updated_at": "2021-09-09T12:00:00Z",
                                "resource_type": "secret",
                                "spec": {
                                    "name": "test-secret",
                                    "description": "test-secret",
                                    "data": {"key": "value"},
                                },
                            }
                        ],
                    },
                }
            )
        ]
        with patch.object(client.PRAXClient, "_request") as mock_request:
            mock_request.return_value = (response, None)
            result = runner.invoke(main, ["prax", "describe", "user"])
            assert result.exit_code == 0
            assert "test-user" in result.output
            assert "test-project" in result.output
            assert "test-secret" in result.output
