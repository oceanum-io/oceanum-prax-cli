from unittest import TestCase
from pathlib import Path
from datetime import datetime, timezone
import requests
from unittest.mock import patch, MagicMock
from oceanum.cli.prax import main, project, route, user, models
from oceanum.cli.prax.main import prax
from oceanum.cli import main
from oceanum.cli.models import ContextObject, TokenResponse, Auth0Config
from click.testing import CliRunner
from click.globals import get_current_context

class TestPRAXCommands(TestCase):

    def setUp(self) -> None:
        self.runner = CliRunner()
        self.specfile = Path(__file__).parent / 'data/dpm-project.yaml'
        return super().setUp()
    
    def test_help(self):
        result = self.runner.invoke(prax, ['--help'])
        assert result.exit_code == 0

    def test_describe_help(self):
        result = self.runner.invoke(prax, ['describe', '--help'])
        assert result.exit_code == 0

    def test_list_help(self):
        result = self.runner.invoke(prax, ['list', '--help'])
        assert result.exit_code == 0

    def test_create_help(self):
        result = self.runner.invoke(prax, ['create', '--help'])
        assert result.exit_code == 0
    
    def test_delete_help(self):
        result = self.runner.invoke(prax, ['delete', '--help'])
        assert result.exit_code == 0

    def test_update_help(self):
        result = self.runner.invoke(prax, ['update', '--help'])
        assert result.exit_code == 0

    def test_submit_help(self):
        result = self.runner.invoke(prax, ['submit', '--help'])
        assert result.exit_code == 0

    def test_terminate_help(self):
        result = self.runner.invoke(prax, ['terminate', '--help'])
        assert result.exit_code == 0
    
    def test_download_help(self):
        result = self.runner.invoke(prax, ['download', '--help'])
        assert result.exit_code == 0

    def test_allow_help(self):
        result = self.runner.invoke(prax, ['allow', '--help'])
        assert result.exit_code == 0

    def test_lists_help(self):
        result = self.runner.invoke(prax, ['list', '--help'])
        assert result.exit_code == 0
    
    def test_validate_help(self):
        result = self.runner.invoke(prax, ['validate', '--help'])
        assert result.exit_code == 0

    def test_deploy_help(self):
        result = self.runner.invoke(prax, ['deploy', '--help'])
        assert result.exit_code == 0


    