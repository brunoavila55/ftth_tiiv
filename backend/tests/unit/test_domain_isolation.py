import importlib
import sys
from unittest.mock import patch


def test_domain_modules_import_without_database_access() -> None:
    """Verifica que a importação de módulos de domínio não efetua conexões nem acessa o banco."""
    modules_to_test = [
        "app.modules.identity",
        "app.modules.inventory",
        "app.modules.cables",
        "app.modules.gis",
        "app.modules.connectivity",
        "app.modules.topology",
        "app.modules.optical",
        "app.modules.customers",
        "app.modules.attachments",
        "app.modules.imports",
        "app.modules.reports",
        "app.modules.audit",
        "app.db.base",
    ]

    with patch("sqlalchemy.engine.base.Engine.connect") as mock_connect:
        mock_connect.side_effect = RuntimeError(
            "DB access is strictly prohibited on module import!"
        )

        for mod_name in modules_to_test:
            if mod_name in sys.modules:
                importlib.reload(sys.modules[mod_name])
            else:
                importlib.import_module(mod_name)

        # Assegura que connect() nunca foi chamado
        assert mock_connect.call_count == 0
