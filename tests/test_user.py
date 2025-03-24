from unittest import TestCase
from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from oceanum.cli.main import main
from oceanum.cli.prax import models, client

runner = CliRunner()


class TestUser(TestCase):

    def test_create_user_secret_help(self):
        result = runner.invoke(main, ['prax', 'create', 'user-secret', '--help'])
        assert result.exit_code == 0

    def test_create_user_secret(self):
        user_get_response = MagicMock(status_code=200)
        user_get_response.json.return_value = [{
            'username': 'test-user',
            'email': 'test-user@test.com',
            'token': 'test-token',
            'current_org': 'test-org',
            'deployable_orgs': ['test-org'],
            'admin_orgs': ['test-org'],
            'orgs': [{
                'name': 'test-org',
                'projects': ['test-project'],
                'tier': {
                    'name': 'test-tier',
                },
                'usage': {
                    'name': 'usage',
                },
                'resources': [],
            }],
            'projects': [],
        }]
        create_response = MagicMock(status_code=201)
        create_response.json.return_value = {
            'name': 'test-secret',
            'data': {'key': 'value'},
        }
        with patch.object(client.PRAXClient, '_get') as mock_request:
            mock_request.return_value = (user_get_response, None)
            with patch.object(client.PRAXClient, '_post') as mock_request:
                mock_request.return_value = (create_response, None)
                result = runner.invoke(main, [
                    'prax', 'create', 'user-secret', 'test-secret', '--data', 'key=value'
                ])
                assert result.exit_code == 0
                assert 'test-secret' in result.output

    def test_describe_user(self):
        response = MagicMock(status_code=200)
        response.json.return_value = [
            {
                'username': 'test-user',
                'email': 'test-user@test.com',
                'token': 'test-token',
                'current_org': 'test-org',
                'deployable_orgs': ['test-org'],
                'admin_orgs': ['test-org'],
                'projects': ['test-project'],
                'resources': [
                    {
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
                    }
                ],
            }
        ]
        with patch.object(client.PRAXClient, '_get') as mock_request:
            mock_request.return_value = (response, None)
            result = runner.invoke(main, ['prax', 'describe', 'user'])
            print(result)
            assert result.exit_code == 0
            assert 'test-user' in result.output