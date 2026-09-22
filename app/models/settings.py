import re
from ipaddress import ip_address
from enum import Enum, StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.proxy import ShadowsocksMethods

from .notification_enable import NotificationEnable
from .validators import DiscordValidator, ProxyValidator, URLValidator

TELEGRAM_TOKEN_PATTERN = r"^\d{8,12}:[A-Za-z0-9_-]{35}$"
BUILTIN_FORMAT_VARIABLES = {
    "SERVER_IP",
    "SERVER_IPV6",
    "USERNAME",
    "DATA_USAGE",
    "DATA_LIMIT",
    "DATA_LEFT",
    "DAYS_LEFT",
    "EXPIRE_DATE",
    "JALALI_EXPIRE_DATE",
    "TIME_LEFT",
    "STATUS_EMOJI",
    "USAGE_PERCENTAGE",
    "ADMIN_USERNAME",
    "PROFILE_TITLE",
    "PROTOCOL",
    "TRANSPORT",
    "url",
    "format",
}
BUILTIN_CUSTOM_VARIABLE_KEYS = {variable.upper() for variable in BUILTIN_FORMAT_VARIABLES}


class RunMethod(StrEnum):
    WEBHOOK = "webhook"
    LONGPOLLING = "long-polling"


class Telegram(BaseModel):
    enable: bool = Field(default=False)
    token: str | None = Field(default=None)
    webhook_url: str | None = Field(default=None)
    webhook_secret: str | None = Field(default=None)
    proxy_url: str | None = Field(default=None)
    method: RunMethod = Field(default=RunMethod.WEBHOOK)

    mini_app_login: bool = Field(default=True)
    mini_app_web_url: str | None = Field(default="")

    for_admins_only: bool = Field(default=True)

    @field_validator("mini_app_web_url")
    @classmethod
    def validate_mini_app_web_url(cls, v):
        return URLValidator.validate_url(v)

    @field_validator("webhook_url")
    def validate_webhook_url(cls, v, values):
        method = values.data.get("method", "webhook")
        if method == "webhook":
            return URLValidator.validate_url(v)

    @field_validator("proxy_url")
    @classmethod
    def validate_proxy_url(cls, v):
        return ProxyValidator.validate_proxy_url(v)

    @field_validator("token")
    @classmethod
    def token_validation(cls, v):
        if not v:
            return v
        if not re.match(TELEGRAM_TOKEN_PATTERN, v):
            raise ValueError("Invalid telegram token format")
        return v

    @model_validator(mode="after")
    def check_enable_requires_token_and_url(self):
        if self.enable and (
            (self.method == RunMethod.WEBHOOK and (not self.token or not self.webhook_url or not self.webhook_secret))
            or (self.method == RunMethod.LONGPOLLING and not self.token)
        ):
            if self.method == RunMethod.WEBHOOK:
                raise ValueError("Telegram bot cannot be enabled without token, webhook_url and webhook_secret.")
            elif self.method == RunMethod.LONGPOLLING:
                raise ValueError("Telegram bot cannot be enabled without token.")
        return self


class WebhookInfo(BaseModel):
    url: str
    secret: str


class Webhook(BaseModel):
    enable: bool = Field(default=False)
    webhooks: list[WebhookInfo] = Field(default=[])
    days_left: list[int] = Field(default=[])
    usage_percent: list[int] = Field(default=[])
    timeout: int = Field(gt=0)
    recurrent: int = Field(gt=0)
    proxy_url: str | None = Field(default=None)

    @field_validator("proxy_url", mode="before")
    @classmethod
    def validate_proxy_url(cls, v):
        return ProxyValidator.validate_proxy_url(v)

    @model_validator(mode="after")
    def check_enable_requires_webhookinfo(self):
        if self.enable and (not self.webhooks or len(self.webhooks) == 0):
            raise ValueError("Webhook cannot be enabled without at least one WebhookInfo.")
        return self


class NotificationChannel(BaseModel):
    """Channel configuration for sending notifications to a specific entity"""

    telegram_chat_id: int | None = Field(default=None)
    telegram_topic_id: int | None = Field(default=None)
    discord_webhook_url: str | None = Field(default=None)

    @field_validator("discord_webhook_url", mode="before")
    @classmethod
    def validate_discord_webhook(cls, value):
        return DiscordValidator.validate_webhook(value)


class NotificationChannels(BaseModel):
    """Per-object notification channels"""

    admin: NotificationChannel = Field(default_factory=NotificationChannel)
    admin_role: NotificationChannel = Field(default_factory=NotificationChannel)
    core: NotificationChannel = Field(default_factory=NotificationChannel)
    group: NotificationChannel = Field(default_factory=NotificationChannel)
    host: NotificationChannel = Field(default_factory=NotificationChannel)
    node: NotificationChannel = Field(default_factory=NotificationChannel)
    user: NotificationChannel = Field(default_factory=NotificationChannel)
    user_template: NotificationChannel = Field(default_factory=NotificationChannel)
    api_key: NotificationChannel = Field(default_factory=NotificationChannel)


class NotificationSettings(BaseModel):
    # Define Which Notfication System Work's
    notify_telegram: bool = Field(default=False)
    notify_discord: bool = Field(default=False)

    # Telegram Settings
    telegram_api_token: str | None = Field(default=None)

    # Fallback Telegram Channel
    telegram_chat_id: int | None = Field(default=None)
    telegram_topic_id: int | None = Field(default=None)

    # Fallback Discord Settings
    discord_webhook_url: str | None = Field(default=None)

    # Per-object notification channels
    channels: NotificationChannels = Field(default_factory=NotificationChannels)

    # Proxy Settings
    proxy_url: str | None = Field(default=None)

    max_retries: int = Field(gt=1)

    @field_validator("proxy_url", mode="before")
    @classmethod
    def validate_proxy_url(cls, v):
        return ProxyValidator.validate_proxy_url(v)

    @field_validator("discord_webhook_url", mode="before")
    @classmethod
    def validate_discord_webhook(cls, value):
        return DiscordValidator.validate_webhook(value)

    @model_validator(mode="after")
    def check_notify_discord_requires_url(self):
        if self.notify_discord and not self.discord_webhook_url:
            raise ValueError("Discord notification cannot be enabled without webhook url.")
        return self

    @model_validator(mode="after")
    def check_notify_telegram_requires_token_and_id(self):
        if self.notify_telegram and not self.telegram_api_token:
            raise ValueError("Telegram notification cannot be enabled without token.")
        if self.notify_telegram and not self.telegram_chat_id:
            raise ValueError("Telegram notification cannot be enabled without chat id.")
        return self


class ConfigFormat(str, Enum):
    links = "links"
    links_base64 = "links_base64"
    xray = "xray"
    wireguard = "wireguard"
    sing_box = "sing_box"
    clash = "clash"
    clash_meta = "clash_meta"
    outline = "outline"
    block = "block"


class SubRule(BaseModel):
    pattern: str
    target: ConfigFormat
    response_headers: dict[str, Any] = Field(default_factory=dict)


class SubFormatEnable(BaseModel):
    links: bool = Field(default=True)
    links_base64: bool = Field(default=True)
    xray: bool = Field(default=True)
    wireguard: bool = Field(default=True)
    sing_box: bool = Field(default=True)
    clash: bool = Field(default=True)
    clash_meta: bool = Field(default=True)
    outline: bool = Field(default=True)


class Platform(StrEnum):
    ANDROID = "android"
    IOS = "ios"
    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"
    APPLETV = "appletv"
    ANDROIDTV = "androidtv"


class Language(StrEnum):
    FA = "fa"
    EN = "en"
    RU = "ru"
    ZH = "zh"


class DownloadLink(BaseModel):
    name: str = Field(max_length=64)
    url: str
    language: Language


class Application(BaseModel):
    name: str = Field(max_length=32)
    icon_url: str = Field(default="", max_length=512)
    import_url: str = Field(default="", max_length=256)
    description: dict[Language, str] = Field(default_factory=dict)
    recommended: bool = Field(False)
    show_when_hwid_enabled: bool = Field(False)
    platform: Platform
    download_links: list[DownloadLink]

    @field_validator("import_url")
    @classmethod
    def validate_import_url(cls, v: str) -> str:
        """Validate import_url contains {url} if not empty."""
        if v and "{url}" not in v:
            raise ValueError("import_url must contain {url} placeholder for URL replacement")
        return v


class CustomVariable(BaseModel):
    key: str = Field(max_length=64)
    value: str = Field(default="", max_length=512)

    @field_validator("key", mode="before")
    @classmethod
    def normalize_key(cls, value):
        if not isinstance(value, str):
            raise TypeError("Variable key must be a string")
        value = value.strip()
        if value.startswith("{") and value.endswith("}"):
            value = value[1:-1].strip()
        return value.upper()

    @field_validator("key")
    @classmethod
    def validate_key(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", value):
            raise ValueError("Variable key must use uppercase letters, numbers, and underscores")
        return value

    @field_validator("value")
    @classmethod
    def validate_value_format(cls, value: str) -> str:
        try:
            value.format_map({key: "" for key in BUILTIN_FORMAT_VARIABLES})
        except ValueError:
            raise ValueError("Invalid formatting variables")
        except KeyError:
            pass
        return value


def validate_custom_variables(value: list[CustomVariable]) -> list[CustomVariable]:
    seen: set[str] = set()
    for variable in value:
        if variable.key.upper() in BUILTIN_CUSTOM_VARIABLE_KEYS:
            raise ValueError(f"Custom variable {variable.key} conflicts with a built-in variable")
        if variable.key in seen:
            raise ValueError(f"Duplicate custom variable {variable.key}")
        seen.add(variable.key)
    return value


class Subscription(BaseModel):
    url_prefix: str = Field(default="")
    update_interval: int = Field(default=12)
    support_url: str = Field(default="https://t.me/")
    profile_title: str = Field(default="Subscription")
    # only supported by v2RayTun and Happ apps
    announce: str = Field(default="", max_length=128)
    announce_url: str = Field(default="")
    response_headers: dict[str, Any] = Field(default_factory=dict)
    # Rules To Seperate Clients And Send Config As Needed
    rules: list[SubRule]
    manual_sub_request: SubFormatEnable = Field(default_factory=SubFormatEnable)
    applications: list[Application] = Field(default_factory=list)
    allow_browser_config: bool = Field(default=True)
    disable_sub_template: bool = Field(default=False)
    randomize_order: bool = Field(default=False)
    custom_variables: list[CustomVariable] = Field(default_factory=list)

    @field_validator("custom_variables")
    @classmethod
    def validate_custom_variables(cls, value: list[CustomVariable]) -> list[CustomVariable]:
        return validate_custom_variables(value)

    @field_validator("applications")
    @classmethod
    def validate_recommended_apps(cls, v: list[Application]) -> list[Application]:
        """Validate that each platform has at most one recommended app per subscription type."""
        platform_recommended = {}

        for app in v:
            if app.recommended:
                recommendation_key = (app.platform, app.show_when_hwid_enabled)
                if recommendation_key in platform_recommended:
                    subscription_type = "device-bound" if app.show_when_hwid_enabled else "standard"
                    raise ValueError(
                        f"Multiple recommended {subscription_type} applications found for platform '{app.platform}'."
                    )
                platform_recommended[recommendation_key] = app.name

        return v


class HWIDSettings(BaseModel):
    enabled: bool = Field(default=True)
    forced: bool = Field(default=False)
    require_hwid_for_manual_sub: bool = Field(default=False)
    fallback_limit: int | None = Field(default=None, ge=0)
    min_limit: int | None = Field(default=None, ge=0)
    max_limit: int | None = Field(default=None, ge=0)


DEFAULT_REALITY_SNI_POOL = [
    "www.microsoft.com",
    "www.cloudflare.com",
    "www.apple.com",
    "www.google.com",
    "www.mozilla.org",
    "www.github.com",
    "www.wikipedia.org",
    "www.amazon.com",
    "www.linkedin.com",
    "www.dropbox.com",
    "www.adobe.com",
    "www.oracle.com",
    "www.ibm.com",
    "www.salesforce.com",
    "www.reddit.com",
]


def normalize_reality_sni_pool(value: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in value:
        host = item.strip().lower()
        if not host:
            continue
        if len(host) > 253:
            raise ValueError("Reality SNI must be at most 253 characters.")
        if "://" in host or "/" in host or ":" in host or any(ch.isspace() for ch in host):
            raise ValueError(f"Invalid Reality SNI: {item}")
        if host not in seen:
            seen.add(host)
            result.append(host)
    return result


class ManagedDomain(BaseModel):
    id: str = Field(max_length=64)
    domain: str = Field(min_length=1, max_length=253)
    node_id: int | None = Field(default=None)
    certificate_method: Literal["letsencrypt", "cloudflare", "existing"] = Field(default="letsencrypt")
    address_mode: Literal["additional", "alias", "both"] = Field(default="additional")
    protocols: list[str] = Field(default_factory=list, max_length=20)
    email: str | None = Field(default=None, max_length=320)
    auto_renew: bool = Field(default=True)
    status: Literal["pending", "active", "expiring", "failed"] = Field(default="pending")
    certificate_expires_at: str | None = Field(default=None, max_length=64)
    last_checked_at: str | None = Field(default=None, max_length=64)

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, value: str) -> str:
        host = value.strip().lower()
        if not host or "://" in host or "/" in host or ":" in host or any(ch.isspace() for ch in host):
            raise ValueError("Invalid domain")
        if not re.fullmatch(r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\\.)+[a-z]{2,63}", host):
            raise ValueError("Invalid domain")
        return host


class ManagedServerAddress(BaseModel):
    id: str = Field(max_length=64)
    node_id: int | None = Field(default=None)
    address: str = Field(min_length=1, max_length=253)
    enabled: bool = Field(default=True)

    @field_validator("address")
    @classmethod
    def validate_address(cls, value: str) -> str:
        address = value.strip().lower()
        if not address or "://" in address or "/" in address or any(ch.isspace() for ch in address):
            raise ValueError("Invalid server address")
        try:
            ip_address(address)
            return address
        except ValueError:
            if not re.fullmatch(r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", address):
                raise ValueError("Invalid server address")
            return address


class General(BaseModel):
    default_method: ShadowsocksMethods = Field(default=ShadowsocksMethods.CHACHA20_POLY1305)
    custom_variables: list[CustomVariable] | None = Field(default=None)
    reality_sni_pool: list[str] = Field(default_factory=lambda: DEFAULT_REALITY_SNI_POOL.copy(), max_length=100)
    primary_domain: ManagedDomain | None = Field(default=None)
    domains: list[ManagedDomain] = Field(default_factory=list, max_length=100)
    server_addresses: list[ManagedServerAddress] = Field(default_factory=list, max_length=200)

    @field_validator("reality_sni_pool")
    @classmethod
    def validate_reality_sni_pool(cls, value: list[str]) -> list[str]:
        return normalize_reality_sni_pool(value)

    @field_validator("custom_variables")
    @classmethod
    def validate_custom_variables(cls, value: list[CustomVariable] | None) -> list[CustomVariable] | None:
        if value is None:
            return None
        return validate_custom_variables(value)


class SettingsSchema(BaseModel):
    telegram: Telegram | None = Field(default=None)
    webhook: Webhook | None = Field(default=None)
    notification_settings: NotificationSettings | None = Field(default=None)
    notification_enable: NotificationEnable | None = Field(default=None)
    subscription: Subscription | None = Field(default=None)
    hwid: HWIDSettings | None = Field(default=None)
    general: General | None = Field(default=None)

    model_config = ConfigDict(from_attributes=True)
