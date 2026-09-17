import sys
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cli.bootstrap_admin import main as cli_bootstrap_main
from app.core.security import verify_password
from app.modules.identity.models import User
from app.schemas.common import UserRole


def test_cli_bootstrap_create_and_reset(db_session: Session) -> None:
    # 1. Cria admin inicial
    test_args = [
        "bootstrap_admin.py",
        "--email",
        "cli_admin@provedor.com.br",
        "--name",
        "Admin CLI Teste",
        "--password",
        "SenhaAdminCli123!",
    ]
    with patch.object(sys, "argv", test_args):
        exit_code = cli_bootstrap_main()
        assert exit_code == 0

    user = db_session.scalar(select(User).where(User.email == "cli_admin@provedor.com.br"))
    assert user is not None
    assert user.name == "Admin CLI Teste"
    assert user.role == UserRole.ADMIN.value
    assert user.is_active is True
    assert verify_password(user.password_hash, "SenhaAdminCli123!")

    # 2. Tenta criar novamente sem --reset-password (deve falhar com 1)
    with patch.object(sys, "argv", test_args):
        exit_code_dup = cli_bootstrap_main()
        assert exit_code_dup == 1

    # 3. Redefine senha com --reset-password (deve suceder com 0)
    reset_args = [
        "bootstrap_admin.py",
        "--email",
        "cli_admin@provedor.com.br",
        "--password",
        "NovaSenhaAdminCli456!",
        "--reset-password",
    ]
    with patch.object(sys, "argv", reset_args):
        exit_code_reset = cli_bootstrap_main()
        assert exit_code_reset == 0

    db_session.expire_all()
    updated_user = db_session.scalar(select(User).where(User.email == "cli_admin@provedor.com.br"))
    assert updated_user is not None
    assert verify_password(updated_user.password_hash, "NovaSenhaAdminCli456!")
