from unittest import TestCase
from unittest.mock import patch, MagicMock

from datetime import datetime, timezone
import requests

from click.testing import CliRunner


from oceanum.cli.main import main
from oceanum.cli.prax import models, client

runner = CliRunner()

route_schema = models.RouteSchema(
    id='test-route-id',
    name='test-route',
    org='test-org',
    display_name='test-route',
    created_at=datetime.now(tz=timezone.utc),
    updated_at=datetime.now(tz=timezone.utc),
    project='test-project',
    stage='test-stage',
    status='active',
    url='http://test-route',
)

class TestAllowProject(TestCase):

    def test_list_notebooks(self):
        response = MagicMock(status_code=200)
        response.json.return_value = [
            route_schema.model_copy(
                update={'notebook':True}
            ).model_dump()
        ]
        with patch('requests.request', return_value=response) as mock_request:
            result = runner.invoke(main, ['prax', 'list', 'notebooks'])
            print(result.output)
            assert result.exit_code == 0
            assert 'test-route' in result.output
    
    def test_allow_help(self):
        result = runner.invoke(main, ['prax', 'allow', 'project', '--help'])
        assert result.exit_code == 0

    def test_allow_route_not_found(self):
        response = MagicMock(status_code=404)
        response.json.return_value = {'detail': 'not found!'}
        response.raise_for_status.side_effect = requests.exceptions.HTTPError('404')
        with patch('requests.request', return_value=response) as mock_request:
            result = runner.invoke(main, ['prax', 'allow', 'route', 'some-random-route','--user','some-user'])
            assert result.exit_code == 1
            assert mock_request.call_count == 1

    def test_allow_route(self):
        post_response = models.ResourcePermissionsSchema(
            users=[],
            groups=[],
        )
        with patch.object(client.PRAXClient, 'get_route', return_value=route_schema) as mock_request:
            with patch.object(client.PRAXClient, '_request', return_value=(post_response, None)) as mock_request:
                result = runner.invoke(main, ['prax', 'allow', 'route', 'test-route','--user','some-user','--change'])
                assert result.exit_code == 0
