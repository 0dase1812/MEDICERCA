"""Application configuration loaded from environment variables."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "MediCerca API"
    environment: str = "local"

    # Central database: identities, affiliations, IPS registry and catalogue.
    database_url: str = "postgresql+psycopg2://medicerca:medicerca@db_central:5432/medicerca"

    # Demo connection secrets. Real URLs never live in a database table.
    database_url_ips_1: str = "postgresql+psycopg2://medicerca:medicerca@db_ips1:5432/ips1"
    database_url_ips_2: str = "postgresql+psycopg2://medicerca:medicerca@db_ips2:5432/ips2"
    database_url_ips_3: str = "postgresql+psycopg2://medicerca:medicerca@db_ips3:5432/ips3"

    # True only for local demo. A deployed environment must apply Alembic migrations.
    auto_create_schema: bool = True

    secret_key: str = "CAMBIA-ESTA-LLAVE-EN-PRODUCCION"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8
    email_modo: str = "simulado"

    # reCAPTCHA v2 (Google). Si queda vacio, no se verifica nada (local/pruebas);
    # en produccion se configura con una clave real para proteger registro y login.
    recaptcha_secret_key: str = ""

    # Correo real (Brevo). Si queda vacio, no se envia nada (mismo criterio que
    # email_modo="simulado": util para desarrollo sin necesitar una cuenta real).
    brevo_api_key: str = ""
    email_remitente: str = "no-responder@medicerca.demo"
    email_remitente_nombre: str = "MediCerca"

    # Clave compartida para los endpoints de administración (ej. crear regentes).
    # No es un reemplazo de un sistema de roles de admin real, es un mínimo viable
    # mientras el modelo de datos solo distingue paciente/regente.
    admin_key: str = "CAMBIA-ESTA-LLAVE-ADMIN-EN-PRODUCCION"

    # Orígenes permitidos por CORS, separados por coma. En producción debe apuntar
    # solo al/los dominio(s) reales del frontend — nunca "*" junto con endpoints
    # autenticados (permite a cualquier sitio leer respuestas con el token puesto).
    cors_origins: str = "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins_list(self) -> list[str]:
        return [origen.strip() for origen in self.cors_origins.split(",") if origen.strip()]

    def verificar_config_produccion(self) -> None:
        """Falla rápido si el despliegue no es local/dev y quedaron secretos de ejemplo.

        Sin este chequeo, un despliegue real podría arrancar tranquilamente firmando
        tokens con la llave de ejemplo del repositorio, o dejando el endpoint de
        administración protegido por una clave que cualquiera puede leer en GitHub.
        """
        if self.environment in ("local", "development", "test"):
            return
        valores_por_defecto = {
            # nosec B105: no es una credencial real, es el valor canario que
            # este mismo método usa para detectar que nadie lo cambió.
            "secret_key": "CAMBIA-ESTA-LLAVE-EN-PRODUCCION",
            "admin_key": "CAMBIA-ESTA-LLAVE-ADMIN-EN-PRODUCCION",
        }
        for campo, valor_por_defecto in valores_por_defecto.items():
            if getattr(self, campo) == valor_por_defecto:
                raise RuntimeError(
                    f"Configuración insegura: '{campo}' sigue con el valor de ejemplo del "
                    f"repositorio y ENVIRONMENT='{self.environment}'. Genere un valor real "
                    f"(ej. `openssl rand -hex 32`) antes de desplegar."
                )

    @property
    def ips_connection_registry(self) -> dict[str, str]:
        """Technical connection registry for the current deployment.

        The central `ips` table stores an opaque `clave_conexion`; this mapping
        resolves it to a URL that stays in configuration, not in the database.
        """
        return {
            "demo_ips_1": self.database_url_ips_1,
            "demo_ips_2": self.database_url_ips_2,
            "demo_ips_3": self.database_url_ips_3,
        }

    def database_url_for_ips_connection(self, clave_conexion: str) -> str:
        try:
            return self.ips_connection_registry[clave_conexion]
        except KeyError as exc:
            raise ValueError(f"No configured connection exists for IPS key '{clave_conexion}'") from exc


settings = Settings()
