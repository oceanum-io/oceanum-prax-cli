from unittest import TestCase
from pathlib import Path
from datetime import datetime, timezone
import requests
from unittest.mock import patch, MagicMock
from oceanum.cli.prax import main, project, route, user, models
from oceanum.cli.prax.main import prax
from oceanum.cli.main import main
from oceanum.cli.common.models import ContextObject, TokenResponse, Auth0Config
from click.testing import CliRunner
from click.globals import get_current_context

class TestPRAXCommands(TestCase):

    def setUp(self) -> None:
        self.runner = CliRunner()
        self.specfile = Path(__file__).parent / 'data/dpm-project.yaml'
        return super().setUp()

    def test_describe_help(self):
        result = self.runner.invoke(prax, ['describe', '--help'])
        assert result.exit_code == 0


    def test_describe_route(self):
        route = models.RouteSchema(
            id='test-route-id',
            name='test-route',
            org='test-org',
            display_name='test-route',
            created_at=datetime.now().replace(tzinfo=timezone.utc),
            updated_at=datetime.now().replace(tzinfo=timezone.utc),
            project='test-project',
            stage='test-stage',
            tier='frontend',
            status='active',
            url='http://test-route'
        )
        with patch('oceanum.cli.prax.client.PRAXClient.get_route', return_value=route) as mock_get:
            result = self.runner.invoke(main, ['prax','describe','route','test-route'])
            assert result.exit_code == 0
            mock_get.assert_called_once_with('test-route')
    
    def test_describe_route_not_found(self):
        result = self.runner.invoke(main, ['prax','describe','route','test-route'])
        assert result.exit_code != 0

    def test_list_routes(self):
        with patch('oceanum.cli.prax.client.PRAXClient.list_routes') as mock_list:
            result = self.runner.invoke(main, ['prax','list','routes'])
            assert result.exit_code == 0
            mock_list.assert_called_once_with()
    
    def test_list_routes_apps(self):
        with patch('oceanum.cli.prax.client.PRAXClient.list_routes') as mock_list:
            result = self.runner.invoke(main, ['prax','list','routes','--tier','frontend'])
            assert result.exit_code == 0
            mock_list.assert_called_once_with(tier='frontend')
    
    def test_list_routes_services(self):
        with patch('oceanum.cli.prax.client.PRAXClient.list_routes') as mock_list:
            result = self.runner.invoke(main, ['prax','list','routes','--tier','backend'])
            print(result.output)
            assert result.exit_code == 0
            
            mock_list.assert_called_once_with(tier='backend')

    def test_list_routes_open(self):
        with patch('oceanum.cli.prax.client.PRAXClient.list_routes') as mock_list:
            result = self.runner.invoke(main, ['prax','list','routes','--open-access'])
            assert result.exit_code == 0
            mock_list.assert_called_once_with(open=True)

    def test_list_no_routes(self):
        with patch('oceanum.cli.prax.client.PRAXClient.list_routes') as mock_list:
            mock_list.return_value = []
            result = self.runner.invoke(main, ['prax','list','routes'])
            assert result.exit_code == 0
