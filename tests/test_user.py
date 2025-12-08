from unittest import TestCase
from unittest.mock import patch

from click.testing import CliRunner

from oceanum.cli import main
from oceanum.cli.prax import models, client, user

runner = CliRunner()


class TestUser(TestCase):

    def test_create_user_secret_help(self):
        result = runner.invoke(main, ['prax', 'create', 'user-secret', '--help'])
        assert result.exit_code == 0

    def test_create_user_secret(self):
        user_get_response = [models.UserSchema(**{
            'username': 'test-user',
            'email': 'test-user@test.com',
            'token': 'test-token',
            'deployable_orgs': ['test-org'],
            'admin_orgs': ['test-org'],
            'current_org': {
                'name': 'test-org',
                'projects': ['test-project'],
                'tier': {
                    'name': 'test-tier',
                },
                'usage': {
                    'name': 'usage',
                },
                'resources': [],
            },
            'projects': [],
        })]
        create_response = models.SecretSpec(
            name='test-secret',
            description='test-secret',
            data=models.SecretData(root={'key': models.SecretStr('value')}),
        )

        with patch.object(client.PRAXClient, 'get_users') as get_users_mock:
            get_users_mock.return_value = user_get_response
            with patch.object(client.PRAXClient, '_request') as mock_request:
                mock_request.return_value = (create_response, None)
                result = runner.invoke(main, [
                    'prax', 'create', 'user-secret', 'test-secret', '--data', 'key=value'
                ])
                print(result.exc_info)
                assert 'test-secret' in result.output

    def test_describe_user(self):
        response = [
            models.UserSchema(**
            {
                "id": "test-user-id",
                'username': 'test-user',
                'email': 'test-user@test.com',
                'token': 'test-token',
                'all_orgs': ['test-org'],
                'deployable_orgs': ['test-org'],
                'admin_orgs': ['test-org'],
                'projects': ['test-project'],
                'current_org': {
                    'name': 'test-org',
                    'projects': ['test-project'],
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
                        "name": "basic"
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
                        "name": "usage"
                    },
                    'resources': [{
                        'org': 'test-org',
                        'name': 'test-secret',
                        'created_at': '2021-09-09T12:00:00Z',
                        'updated_at': '2021-09-09T12:00:00Z',
                        'resource_type': 'secret',
                        'spec': {
                            'name': 'test-secret',
                            'description': 'test-secret',
                            'data': {'key': 'value'},
                        }
                    }],
                },
            }
            )
        ]
        with patch.object(client.PRAXClient, '_request') as mock_request:
            mock_request.return_value = (response, None)
            result = runner.invoke(main, ['prax', 'describe', 'user'])
            assert result.exit_code == 0
            assert 'test-user' in result.output
            assert 'test-project' in result.output
            assert 'test-secret' in result.output
