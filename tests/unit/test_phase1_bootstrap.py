"""Smoke tests for Phase 1 bootstrap."""

from unittest.mock import patch

from click.testing import CliRunner

from knowledge_injector.cli.commands import cli
from knowledge_injector.config import AppSettings
from knowledge_injector.containers import Container


class TestConfig:
    def test_app_settings_loads_defaults(self):
        settings = AppSettings.from_env()
        assert settings.app_env in ("dev", "prod", "staging", "test")
        assert settings.embeddings.dimensions == 384
        assert settings.chunking.size == 1000
        assert settings.chunking.overlap == 150

    def test_database_dsn_safe_hides_credentials(self):
        settings = AppSettings.from_env()
        assert settings.database.password not in settings.database.dsn_safe
        assert "@" not in settings.database.dsn_safe

    def test_ingestion_patterns_parsed_from_comma_string(self, monkeypatch):
        monkeypatch.setenv("INGESTION_INCLUDE_PATTERNS", "**/*.md,**/*.txt")
        from knowledge_injector.config import IngestionSettings

        s = IngestionSettings()
        assert "**/*.md" in s.include_patterns
        assert "**/*.txt" in s.include_patterns


class TestContainer:
    def test_container_creates_settings(self):
        container = Container()
        settings = container.settings()
        assert isinstance(settings, AppSettings)

    def test_container_creates_ingestion_service(self):
        from knowledge_injector.application.ingestion_service import IngestionService

        container = Container()
        svc = container.ingestion_service()
        assert isinstance(svc, IngestionService)


class TestCli:
    def test_run_once_exits_zero(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["run-once"])
        assert result.exit_code == 0, result.output

    def test_run_once_logs_source_name(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["run-once"])
        assert "run_once" in result.output or "ingestion" in result.output

    def test_help_lists_commands(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert "run-once" in result.output
        assert "run-loop" in result.output
        assert result.exit_code == 0

    def test_run_loop_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["run-loop", "--help"])
        assert "--interval" in result.output
        assert result.exit_code == 0
