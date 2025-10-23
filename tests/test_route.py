from unittest import TestCase
from unittest.mock import patch, MagicMock

from datetime import datetime, timezone
import requests

from click.testing import CliRunner


from oceanum.cli import main
from oceanum.cli.prax import models, client, route

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

class TestRoutes(TestCase):
    def test_describe_route(self):
        route = models.RouteSchema(
            id='test-route-id',
            name='test-route',
            org='test-org',
            display_name='test-route',
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
            project='test-project',
            stage='test-stage',
            tier='frontend',
            status='active',
            url='http://test-route',
        )
        with patch('oceanum.cli.prax.client.PRAXClient.get_route', return_value=route) as mock_get:
            result = runner.invoke(main, ['prax','describe','route','test-route'])
            assert result.exit_code == 0
            mock_get.assert_called_once_with('test-route')
    
    def test_describe_route_not_found(self):
        result = runner.invoke(main, ['prax','describe','route','test-route'])
        assert result.exit_code != 0

    def test_list_routes(self):
        with patch('oceanum.cli.prax.client.PRAXClient.list_routes') as mock_list:
            mock_list.return_value = models.PagedRouteSchema(items=[route_schema], count=1)
            result = runner.invoke(main, ['prax','list','routes'])
            print(result.output)
            assert result.exit_code == 0
            mock_list.assert_called_once_with(limit=100)
    
    def test_list_routes_apps(self):
        with patch('oceanum.cli.prax.client.PRAXClient.list_routes') as mock_list:
            mock_list.return_value = models.PagedRouteSchema(items=[route_schema], count=1)
            result = runner.invoke(main, ['prax','list','routes','--tier','frontend'])
            assert result.exit_code == 0
            mock_list.assert_called_once_with(tier='frontend', limit=100)

    def test_list_routes_open(self):
        with patch('oceanum.cli.prax.client.PRAXClient.list_routes') as mock_list:
            mock_list.return_value = models.PagedRouteSchema(items=[route_schema], count=1)
            result = runner.invoke(main, ['prax','list','routes','--open-access'])
            assert result.exit_code == 0
            mock_list.assert_called_once_with(open=True, limit=100)

    def test_list_no_routes(self):
        with patch('oceanum.cli.prax.client.PRAXClient.list_routes') as mock_list:
            mock_list.return_value = models.PagedRouteSchema(**{"items": [], "count": 0})
            result = runner.invoke(main, ['prax','list','routes'])
            assert result.exit_code == 0

    def test_list_notebooks(self):
        with patch('oceanum.cli.prax.client.PRAXClient.list_routes') as mock_list:
            mock_list.return_value = models.PagedRouteSchema(items=[
                route_schema.model_copy(update={'notebook':True})
            ], count=1)
            result = runner.invoke(main, ['prax', 'list', 'notebooks'])
            print(result.output)
            assert result.exit_code == 0
            assert 'test-route' in result.output

class TestAllowProject(TestCase):

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
