import argparse
import getpass
import os
import sys

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import get_session_factory
from app.modules.identity.models import User
from app.schemas.common import UserRole


def main() -> int:
    parser = argparse.ArgumentParser(
        description="CLI para criação inicial e recuperação de senha do administrador do FTTH Manager."
    )
    parser.add_argument(
        "--email",
        type=str,
        required=True,
        help="E-mail corporativo do administrador",
    )
    parser.add_argument(
        "--name",
        type=str,
        default="Administrador",
        help="Nome completo do administrador (padrão: Administrador)",
    )
    parser.add_argument(
        "--password",
        type=str,
        default=None,
        help="Senha de acesso (opcional; se omitida, lerá de FTTH_ADMIN_PASSWORD ou solicitará interativamente)",
    )
    parser.add_argument(
        "--reset-password",
        action="store_true",
        help="Permite redefinir a senha e reativar caso o usuário já exista",
    )

    args = parser.parse_args()
    email = args.email.strip().lower()
    name = args.name.strip()
    password = args.password

    if not password:
        password = os.environ.get("FTTH_ADMIN_PASSWORD")

    if not password:
        if not sys.stdin.isatty():
            print(
                "ERRO: A senha deve ser fornecida via argumento --password, variável FTTH_ADMIN_PASSWORD ou terminal interativo.",
                file=sys.stderr,
            )
            return 1
        password = getpass.getpass("Digite a senha do administrador (mínimo 8 caracteres): ")
        password_confirm = getpass.getpass("Confirme a senha: ")
        if password != password_confirm:
            print("ERRO: As senhas digitadas não coincidem.", file=sys.stderr)
            return 1

    if len(password) < 8:
        print("ERRO: A senha deve ter no mínimo 8 caracteres.", file=sys.stderr)
        return 1

    factory = get_session_factory()
    with factory() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user:
            if not args.reset_password:
                print(
                    f"ERRO: O usuário '{email}' já existe no sistema. "
                    f"Passe o argumento --reset-password para redefinir a credencial.",
                    file=sys.stderr,
                )
                return 1

            user.password_hash = hash_password(password)
            user.role = UserRole.ADMIN.value
            user.is_active = True
            user.version += 1
            db.commit()
            print(f"SUCESSO: Credencial do administrador '{email}' redefinida com sucesso.")
            return 0

        new_admin = User(
            email=email,
            name=name,
            password_hash=hash_password(password),
            role=UserRole.ADMIN.value,
            is_active=True,
            version=1,
        )
        db.add(new_admin)
        db.commit()
        print(f"SUCESSO: Administrador inicial '{email}' criado com sucesso.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
