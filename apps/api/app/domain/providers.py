"""Which third-party accounts an organisation can connect, and how.

One list, because the same set has to agree in four places: the API's request
validation, the settings UI, whatever a `voice_agent` row is allowed to name in
its `stt_provider`/`tts_provider`/`llm_provider` columns, and the voice
runtime's own plugin registry.

Pure data, no I/O - the database deliberately holds no allow-list of its own
(`provider_credentials.provider` is a plain non-empty check, widened in the
ADR-4 migration precisely so adding a vendor is an app change rather than a
migration). This module *is* that application-layer list.

Three ideas carry the whole file.

**A provider has roles, not a role.** One Deepgram key does speech-to-text and
text-to-speech; one Azure key does both plus an LLM. Modelling that as a single
role forced a vendor to be listed twice under two ids, and then a credential
stored against one of them was invisible to the other. `roles` is a set, and
there is still exactly one credential row per (org, provider).

**A provider declares its own fields.** Deepgram wants one key. Twilio wants two.
Azure wants a key, a region and an endpoint; AWS wants three; PlayAI wants a user
id alongside its key. `CredentialField` is what lets the settings page render a
vendor it has never seen without the frontend knowing anything about it.

**`runtime_extra` is the honest half.** It names the `apps/voice-runtime` extra
that installs the plugin able to drive this provider. `None` means CallFlow will
store the credential and *nothing consumes it yet* - true of storage,
automation and observability vendors, which have no recording, tool-calling or
tracing behind them to connect to. The interface says so in those words rather
than showing them as connected (CLAUDE.md non-negotiable #9): the key really is
saved, and the integration really is doing nothing, and both halves are stated.

`ConnectMethod` is honest in the same way. Only OpenRouter offers a login flow
we have actually verified (documented OAuth PKCE). Twilio Connect, Slack, HubSpot
and Salesforce all have OAuth, but each needs an app registered and approved
first; until that exists, claiming a login button would be claiming something
that does not work.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ProviderRole(str, Enum):
    """What a credential is *for*.

    The first three mirror `voice_agents`' own columns rather than inventing a
    second taxonomy - an org needs one from each before a call can happen, and
    that is the thing the settings page has to make obvious.
    """

    TRANSCRIBER = "transcriber"
    VOICE = "voice"
    INTELLIGENCE = "intelligence"
    TELEPHONY = "telephony"
    STORAGE = "storage"
    AUTOMATION = "automation"
    OBSERVABILITY = "observability"


#: Roles a live call actually runs on. Everything else is stored-only today.
CALL_ROLES: frozenset[ProviderRole] = frozenset(
    {
        ProviderRole.TRANSCRIBER,
        ProviderRole.VOICE,
        ProviderRole.INTELLIGENCE,
        ProviderRole.TELEPHONY,
    }
)


class ConnectMethod(str, Enum):
    OAUTH = "oauth"
    """The vendor hosts a login and hands back a key. Verified, not assumed."""

    API_KEY = "api_key"
    """The operator pastes credentials. The only option most vendors offer."""


@dataclass(frozen=True)
class CredentialField:
    """One input on the connect form.

    `key` is what the stored JSON is keyed on and what the adapter reads, so it
    is part of the contract - renaming one orphans every credential already
    stored under the old name.
    """

    key: str
    label: str
    #: Masked on entry and never returned by any read endpoint.
    secret: bool = True
    required: bool = True
    placeholder: str = ""
    #: Shown under the input. Say where in the vendor's console to find it.
    help: str | None = None
    #: Renders a textarea rather than a single line - service-account JSON.
    multiline: bool = False


def _key(label: str = "API key", *, help: str | None = None, ph: str = "") -> CredentialField:
    """The single-secret case, which is most vendors."""
    return CredentialField(key="api_key", label=label, help=help, placeholder=ph)


@dataclass(frozen=True)
class CredentialProbe:
    """One read-only request that proves a credential works.

    Data, not code, for the same reason the credential fields are: there are 57
    providers and a function per vendor would be 57 places to keep in step with
    a catalogue that is already declarative. `services/credential_check.py`
    performs it; nothing in `domain/` does any I/O.

    Always a **read**. Verifying must never create, modify, or spend anything on
    the customer's account - listing what is already there proves the key is
    valid and the account is reachable without side effects.

    `auth` says how the secret is presented:
      `bearer`  - `Authorization: Bearer <value>`
      `basic`   - HTTP basic, `basic_user_field`:`field`
      `header`  - a vendor's own header, named by `header`
      `query`   - a query parameter, named by `header`
    """

    url: str
    #: The credential field whose value authenticates. Interpolated into `url`
    #: too, as `{field}` - Twilio's account SID is part of its path.
    field: str
    auth: str = "bearer"
    header: str | None = None
    basic_user_field: str | None = None
    #: `GET` for a listing endpoint. `POST` for a vendor with no read endpoint
    #: that authenticates - sent with an empty body, so a valid key is refused
    #: for the *body* (4xx naming the missing field) while an invalid one is
    #: refused for the *key*. Nothing is created either way, which is what keeps
    #: a POST probe as read-only in effect as a GET.
    method: str = "GET"
    #: Statuses that mean "the key was accepted, the request was not". Only
    #: meaningful with `method="POST"`, where a probe deliberately sends a body
    #: the vendor must reject.
    accept_statuses: tuple[int, ...] = ()


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    name: str
    roles: frozenset[ProviderRole]
    connect: ConnectMethod
    summary: str
    fields: tuple[CredentialField, ...]
    docs_url: str
    #: The `apps/voice-runtime` extra that installs the plugin driving this.
    #: `None` = stored only; nothing in a call reads it yet.
    runtime_extra: str | None = None
    #: Set when one credential proxies many models, so the agent must also name
    #: which model to run. Drives a required model field on the agent, not here.
    needs_model: bool = False
    #: A short, true note the card shows. Not marketing - a constraint.
    note: str | None = None
    #: How to prove the credential works. `None` = no probe is declared yet, and
    #: the credential is stored unverified rather than claimed to be checked.
    probe: CredentialProbe | None = None

    @property
    def is_verifiable(self) -> bool:
        return self.probe is not None

    @property
    def is_wired(self) -> bool:
        return self.runtime_extra is not None


def _p(
    id: str,
    name: str,
    roles: set[ProviderRole],
    summary: str,
    docs_url: str,
    *,
    fields: tuple[CredentialField, ...] = (),
    connect: ConnectMethod = ConnectMethod.API_KEY,
    runtime_extra: str | None = None,
    needs_model: bool = False,
    note: str | None = None,
    probe: CredentialProbe | None = None,
) -> ProviderSpec:
    return ProviderSpec(
        id=id,
        name=name,
        roles=frozenset(roles),
        connect=connect,
        summary=summary,
        fields=fields or (_key(),),
        docs_url=docs_url,
        runtime_extra=runtime_extra,
        needs_model=needs_model,
        note=note,
        probe=probe,
    )


R = ProviderRole

# --- Intelligence: the model that decides what to say -------------------------
# Everything reachable through the OpenAI plugin's own factories carries
# `runtime_extra="openai"` rather than a package of its own - `with_openrouter`,
# `with_azure`, `with_perplexity` and friends are the supported wiring (ADR-7),
# not a shortcut.

_INTELLIGENCE: tuple[ProviderSpec, ...] = (
    _p(
        "openrouter", "OpenRouter", {R.INTELLIGENCE},
        "One key, hundreds of models.",
        "https://openrouter.ai/keys",
        connect=ConnectMethod.OAUTH, runtime_extra="openai", needs_model=True,
        probe=CredentialProbe("https://openrouter.ai/api/v1/key", "api_key"),
    ),
    _p(
        "openai", "OpenAI", {R.INTELLIGENCE, R.TRANSCRIBER, R.VOICE},
        "GPT, Whisper and OpenAI voices.",
        "https://platform.openai.com/api-keys",
        fields=(_key(ph="sk-…"),), runtime_extra="openai", needs_model=True,
        probe=CredentialProbe("https://api.openai.com/v1/models", "api_key"),
    ),
    _p(
        "anthropic", "Anthropic", {R.INTELLIGENCE},
        "Claude. Follows a brief closely.",
        "https://console.anthropic.com/settings/keys",
        fields=(_key(ph="sk-ant-…"),), runtime_extra="anthropic", needs_model=True,
        probe=CredentialProbe("https://api.anthropic.com/v1/models", "api_key", auth="header", header="x-api-key"),
    ),
    _p(
        "google", "Google Gemini", {R.INTELLIGENCE, R.TRANSCRIBER, R.VOICE},
        "Gemini, plus Cloud speech and voices.",
        "https://aistudio.google.com/apikey",
        fields=(
            _key("API key", help="An AI Studio key covers Gemini."),
            CredentialField(
                key="service_account_json", label="Service account JSON", required=False,
                multiline=True,
                help="Only needed for Google Cloud Speech-to-Text or Text-to-Speech.",
            ),
        ),
        runtime_extra="google", needs_model=True,
        # `x-goog-api-key`, not `?key=`: httpx logs every request URL at INFO,
        # so a secret in the query string reaches the log before any filter
        # can help - and a header never appears there at all. Google accepts
        # both (`ISSUES.md` #167).
        probe=CredentialProbe(
            "https://generativelanguage.googleapis.com/v1beta/models", "api_key",
            auth="header", header="x-goog-api-key",
        ),
    ),
    _p(
        "groq", "Groq", {R.INTELLIGENCE, R.TRANSCRIBER},
        "Fastest inference here.",
        "https://console.groq.com/keys",
        fields=(_key(ph="gsk_…"),), runtime_extra="groq", needs_model=True,
        probe=CredentialProbe("https://api.groq.com/openai/v1/models", "api_key"),
    ),
    _p(
        "xai", "xAI", {R.INTELLIGENCE},
        "Grok models.",
        "https://console.x.ai",
        runtime_extra="xai", needs_model=True,
        probe=CredentialProbe("https://api.x.ai/v1/models", "api_key"),
    ),
    _p(
        "mistral", "Mistral AI", {R.INTELLIGENCE},
        "Strong in French and Spanish.",
        "https://console.mistral.ai/api-keys",
        runtime_extra="mistralai", needs_model=True,
        probe=CredentialProbe("https://api.mistral.ai/v1/models", "api_key"),
    ),
    _p(
        "cerebras", "Cerebras", {R.INTELLIGENCE},
        "Very low latency on Llama.",
        "https://cloud.cerebras.ai",
        runtime_extra="cerebras", needs_model=True,
        probe=CredentialProbe("https://api.cerebras.ai/v1/models", "api_key"),
    ),
    _p(
        "fireworks", "Fireworks AI", {R.INTELLIGENCE},
        "Hosted open models, per token.",
        "https://fireworks.ai/account/api-keys",
        runtime_extra="fireworksai", needs_model=True,
        probe=CredentialProbe("https://api.fireworks.ai/inference/v1/models", "api_key"),
    ),
    _p(
        "together", "Together AI", {R.INTELLIGENCE},
        "Open models at scale.",
        "https://api.together.xyz/settings/api-keys",
        runtime_extra="openai", needs_model=True,
        probe=CredentialProbe("https://api.together.xyz/v1/models", "api_key"),
    ),
    _p(
        "deepseek", "DeepSeek", {R.INTELLIGENCE},
        "Frontier reasoning, far cheaper.",
        "https://platform.deepseek.com/api_keys",
        runtime_extra="openai", needs_model=True,
        probe=CredentialProbe("https://api.deepseek.com/models", "api_key"),
    ),
    _p(
        "perplexity", "Perplexity", {R.INTELLIGENCE},
        "Searches the web while answering.",
        "https://www.perplexity.ai/settings/api",
        fields=(_key(ph="pplx-…"),), runtime_extra="openai", needs_model=True,
    ),
    _p(
        "azure_openai", "Azure OpenAI", {R.INTELLIGENCE},
        "OpenAI under your Azure tenancy.",
        "https://portal.azure.com",
        fields=(
            _key(),
            CredentialField(
                key="endpoint", label="Endpoint", secret=False,
                placeholder="https://your-resource.openai.azure.com",
            ),
            CredentialField(
                key="deployment", label="Deployment name", secret=False,
                help="Azure addresses models by deployment, not by model name.",
            ),
        ),
        runtime_extra="openai",
    ),
    _p(
        "aws_bedrock", "AWS Bedrock", {R.INTELLIGENCE, R.TRANSCRIBER, R.VOICE},
        "Bedrock, Transcribe and Polly.",
        "https://console.aws.amazon.com/bedrock",
        fields=(
            CredentialField(key="access_key_id", label="Access key ID"),
            CredentialField(key="secret_access_key", label="Secret access key"),
            CredentialField(
                key="region", label="Region", secret=False, placeholder="ap-south-1"
            ),
        ),
        runtime_extra="aws", needs_model=True,
    ),
    _p(
        "minimax", "MiniMax", {R.INTELLIGENCE, R.VOICE},
        "Multilingual models and voices.",
        "https://www.minimax.io/platform",
        fields=(
            _key(),
            CredentialField(key="group_id", label="Group ID", secret=False),
        ),
        runtime_extra="minimax", needs_model=True,
    ),
)

# --- Transcriber: turning what the contact said into text ---------------------

_TRANSCRIBER: tuple[ProviderSpec, ...] = (
    _p(
        "deepgram", "Deepgram", {R.TRANSCRIBER, R.VOICE},
        "Fast English speech, plus Aura voices.",
        "https://console.deepgram.com",
        runtime_extra="deepgram",
        probe=CredentialProbe("https://api.deepgram.com/v1/projects", "api_key", auth="header", header="Authorization-Token"),
    ),
    _p(
        "assemblyai", "AssemblyAI", {R.TRANSCRIBER},
        "Accurate English, well formatted.",
        "https://www.assemblyai.com/app/api-keys",
        runtime_extra="assemblyai",
        probe=CredentialProbe("https://api.assemblyai.com/v2/transcript?limit=1", "api_key", auth="header", header="authorization"),
    ),
    _p(
        "gladia", "Gladia", {R.TRANSCRIBER},
        "Built for noisy phone lines.",
        "https://app.gladia.io",
        runtime_extra="gladia",
        probe=CredentialProbe("https://api.gladia.io/v2/pre-recorded", "api_key", auth="header", header="x-gladia-key"),
    ),
    _p(
        "speechmatics", "Speechmatics", {R.TRANSCRIBER},
        "Tells apart who said what.",
        "https://portal.speechmatics.com",
        runtime_extra="speechmatics",
        probe=CredentialProbe("https://asr.api.speechmatics.com/v2/jobs?limit=1", "api_key"),
    ),
    _p(
        "soniox", "Soniox", {R.TRANSCRIBER},
        "60+ languages, one model.",
        "https://console.soniox.com",
        runtime_extra="soniox",
        probe=CredentialProbe("https://api.soniox.com/v1/models", "api_key"),
    ),
    _p(
        "sarvam", "Sarvam", {R.TRANSCRIBER, R.VOICE},
        "Built for Indian languages.",
        "https://dashboard.sarvam.ai",
        fields=(_key("API subscription key"),), runtime_extra="sarvam",
        # NOT `/v1/models`: that endpoint is public - it answers 200 with no
        # key at all, so probing it accepted any string as a valid credential.
        # `/text-to-speech` checks the key before the body, so an empty body
        # separates the two cases without synthesising anything: a good key
        # gets 400 "text must be provided", a bad one 403.
        probe=CredentialProbe(
            "https://api.sarvam.ai/text-to-speech", "api_key",
            auth="header", header="api-subscription-key",
            method="POST", accept_statuses=(400, 422),
        ),
    ),
    _p(
        "azure_speech", "Azure Speech", {R.TRANSCRIBER, R.VOICE},
        "Widest language coverage here.",
        "https://portal.azure.com",
        fields=(
            _key("Subscription key"),
            CredentialField(
                key="region", label="Region", secret=False, placeholder="centralindia",
            ),
        ),
        runtime_extra="azure",
    ),
    _p(
        "clova", "Naver Clova", {R.TRANSCRIBER},
        "Korean speech recognition.",
        "https://www.ncloud.com",
        fields=(
            CredentialField(key="client_id", label="Client ID", secret=False),
            CredentialField(key="client_secret", label="Client secret"),
        ),
        runtime_extra="clova",
    ),
    _p(
        "gnani", "Gnani", {R.TRANSCRIBER, R.VOICE},
        "Indian languages, contact-centre tuned.",
        "https://www.gnani.ai",
        runtime_extra="gnani",
    ),
    _p(
        "rtzr", "ReturnZero", {R.TRANSCRIBER},
        "Korean, strong on phone audio.",
        "https://developers.rtzr.ai",
        fields=(
            CredentialField(key="client_id", label="Client ID", secret=False),
            CredentialField(key="client_secret", label="Client secret"),
        ),
        runtime_extra="rtzr",
    ),
    _p(
        "spitch", "Spitch", {R.TRANSCRIBER, R.VOICE},
        "Yoruba, Igbo, Hausa, Amharic.",
        "https://spi-tch.com",
        runtime_extra="spitch",
    ),
    _p(
        "baseten", "Baseten", {R.TRANSCRIBER},
        "Your own model, dedicated hardware.",
        "https://app.baseten.co/settings/api_keys",
        runtime_extra="baseten",
    ),
    _p(
        "fal", "fal.ai", {R.TRANSCRIBER},
        "Whisper, fast enough to talk to.",
        "https://fal.ai/dashboard/keys",
        runtime_extra="fal",
    ),
)

# --- Voice: how the agent sounds ----------------------------------------------

_VOICE: tuple[ProviderSpec, ...] = (
    _p(
        "elevenlabs", "ElevenLabs", {R.VOICE, R.TRANSCRIBER},
        "For when the voice is the product.",
        "https://elevenlabs.io/app/settings/api-keys",
        runtime_extra="elevenlabs",
        # NOT `/v1/voices`: it answers 200 with no key at all, so probing it
        # accepted any string. `/v1/history` requires a key and, because
        # ElevenLabs keys are scoped per operation, distinguishes all three
        # cases in its message - "Invalid API key" for a wrong one against
        # "missing the permission" for a real one too narrow to read here,
        # which `_is_scope_refusal` keeps rather than rejects.
        probe=CredentialProbe(
            "https://api.elevenlabs.io/v1/history", "api_key",
            auth="header", header="xi-api-key",
        ),
    ),
    _p(
        "cartesia", "Cartesia", {R.VOICE, R.TRANSCRIBER},
        "Lowest time to first audio.",
        "https://play.cartesia.ai/keys",
        runtime_extra="cartesia",
        probe=CredentialProbe("https://api.cartesia.ai/voices", "api_key", auth="header", header="X-API-Key"),
    ),
    _p(
        "playai", "PlayAI", {R.VOICE},
        "PlayHT voices and instant cloning.",
        "https://play.ht/studio/api-access",
        fields=(
            CredentialField(key="user_id", label="User ID", secret=False),
            _key(),
        ),
        runtime_extra="playai",
    ),
    _p(
        "lmnt", "LMNT", {R.VOICE},
        "Priced for high call volume.",
        "https://app.lmnt.com/account",
        runtime_extra="lmnt",
        probe=CredentialProbe("https://api.lmnt.com/v1/ai/voice/list", "api_key", auth="header", header="X-API-Key"),
    ),
    _p(
        "rime", "Rime", {R.VOICE},
        "Sounds like a person, not a narrator.",
        "https://rime.ai/dashboard/tokens",
        runtime_extra="rime",
    ),
    _p(
        "hume", "Hume AI", {R.VOICE},
        "Reads emotional context.",
        "https://platform.hume.ai/settings/keys",
        runtime_extra="hume",
        probe=CredentialProbe("https://api.hume.ai/v0/evi/configs", "api_key", auth="header", header="X-Hume-Api-Key"),
    ),
    _p(
        "inworld", "Inworld", {R.VOICE},
        "Consistent persona across a call.",
        "https://studio.inworld.ai",
        runtime_extra="inworld",
        probe=CredentialProbe("https://api.inworld.ai/tts/v1/voices", "api_key"),
    ),
    _p(
        "neuphonic", "Neuphonic", {R.VOICE},
        "Strong on European languages.",
        "https://neuphonic.com",
        runtime_extra="neuphonic",
        probe=CredentialProbe("https://api.neuphonic.com/voices", "api_key", auth="header", header="X-API-KEY"),
    ),
    _p(
        "resemble", "Resemble AI", {R.VOICE},
        "Cloning, with consent records.",
        "https://app.resemble.ai",
        runtime_extra="resemble",
        probe=CredentialProbe("https://app.resemble.ai/api/v2/projects", "api_key"),
    ),
    _p(
        "speechify", "Speechify", {R.VOICE},
        "Stays clear on a poor line.",
        "https://console.sws.speechify.com",
        runtime_extra="speechify",
        probe=CredentialProbe("https://api.sws.speechify.com/v1/voices", "api_key"),
    ),
    _p(
        "murf", "Murf AI", {R.VOICE},
        "Large library, 20+ languages.",
        "https://murf.ai/api/dashboard",
        runtime_extra="murf",
        probe=CredentialProbe(
            "https://api.murf.ai/v1/speech/voices", "api_key",
            auth="header", header="api-key",
        ),
    ),
    _p(
        "smallestai", "Smallest AI", {R.VOICE},
        "Indian voices, very low latency.",
        "https://waves.smallest.ai",
        runtime_extra="smallestai",
    ),
    _p(
        "fishaudio", "Fish Audio", {R.VOICE},
        "Open models, fast cloning.",
        "https://fish.audio/go-api",
        runtime_extra="fishaudio",
    ),
    _p(
        "upliftai", "Uplift AI", {R.VOICE},
        "Urdu and Pakistani languages.",
        "https://upliftai.org",
        runtime_extra="upliftai",
    ),
)

# --- Telephony: the line the call is placed on --------------------------------

_TELEPHONY: tuple[ProviderSpec, ...] = (
    _p(
        "twilio", "Twilio", {R.TELEPHONY},
        "Your own Twilio number.",
        "https://console.twilio.com",
        fields=(
            CredentialField(key="account_sid", label="Account SID", placeholder="AC…"),
            CredentialField(key="auth_token", label="Auth token"),
        ),
        runtime_extra="carrier",
        # Reads the account itself: proves both halves of the pair, and the
        # SID is part of the path as well as the basic-auth user.
        probe=CredentialProbe(
            "https://api.twilio.com/2010-04-01/Accounts/{field}.json",
            "auth_token", auth="basic", basic_user_field="account_sid",
        ),
        # Twilio Connect exists but needs a Connect App registered and approved.
        # Until that is real, an OAuth button would claim something that is not.
        note="Twilio cannot authenticate inbound SIP, so the trunk is locked to Twilio's own IP ranges instead.",
    ),
    _p(
        "plivo", "Plivo", {R.TELEPHONY},
        "Your own Plivo number.",
        "https://console.plivo.com",
        fields=(
            CredentialField(key="auth_id", label="Auth ID", placeholder="MA…"),
            CredentialField(key="auth_token", label="Auth token"),
        ),
        runtime_extra="carrier",
        probe=CredentialProbe("https://api.plivo.com/v1/Account/{field}/", "auth_token", auth="basic", basic_user_field="auth_id"),
    ),
    _p(
        "telnyx", "Telnyx", {R.TELEPHONY},
        "Own network. Usually cheapest per minute.",
        "https://portal.telnyx.com/#/app/api-keys",
        fields=(
            _key("API key", ph="KEY…"),
            CredentialField(
                key="connection_id", label="SIP connection ID", secret=False, required=False,
                help="Leave empty and CallFlow creates a connection for you.",
            ),
        ),
        runtime_extra="carrier",
        probe=CredentialProbe("https://api.telnyx.com/v2/phone_numbers?page[size]=1", "api_key"),
    ),
    _p(
        "vonage", "Vonage", {R.TELEPHONY},
        "Widest international coverage.",
        "https://dashboard.nexmo.com/settings",
        fields=(
            CredentialField(key="api_key", label="API key", secret=False),
            CredentialField(key="api_secret", label="API secret"),
        ),
        runtime_extra="carrier",
        probe=CredentialProbe("https://rest.nexmo.com/account/get-balance", "api_secret", auth="basic", basic_user_field="api_key"),
    ),
)

# --- Stored only: nothing in a call reads these yet ---------------------------
# Every spec below leaves `runtime_extra` as None on purpose. The credential is
# genuinely encrypted and saved; the feature it would drive - call recording,
# tool-calling, tracing - does not exist. The interface states both.

_STORAGE: tuple[ProviderSpec, ...] = (
    _p(
        "aws_s3", "Amazon S3", {R.STORAGE},
        "Recordings in your own bucket.",
        "https://console.aws.amazon.com/s3",
        fields=(
            CredentialField(key="access_key_id", label="Access key ID"),
            CredentialField(key="secret_access_key", label="Secret access key"),
            CredentialField(key="region", label="Region", secret=False, placeholder="ap-south-1"),
            CredentialField(key="bucket", label="Bucket", secret=False),
        ),
    ),
    _p(
        "gcp_storage", "Google Cloud Storage", {R.STORAGE},
        "Recordings in your own GCS bucket.",
        "https://console.cloud.google.com/storage",
        fields=(
            CredentialField(
                key="service_account_json", label="Service account JSON", multiline=True,
            ),
            CredentialField(key="bucket", label="Bucket", secret=False),
        ),
    ),
    _p(
        "cloudflare_r2", "Cloudflare R2", {R.STORAGE},
        "S3-compatible, no egress fees.",
        "https://dash.cloudflare.com",
        fields=(
            CredentialField(key="account_id", label="Account ID", secret=False),
            CredentialField(key="access_key_id", label="Access key ID"),
            CredentialField(key="secret_access_key", label="Secret access key"),
            CredentialField(key="bucket", label="Bucket", secret=False),
        ),
    ),
)

_AUTOMATION: tuple[ProviderSpec, ...] = (
    _p(
        "make", "Make", {R.AUTOMATION},
        "Trigger a Make scenario.",
        "https://www.make.com",
        fields=(
            _key(),
            CredentialField(
                key="zone", label="Zone", secret=False, placeholder="eu2.make.com",
                help="The host in your Make dashboard URL.",
            ),
        ),
    ),
    _p(
        "n8n", "n8n", {R.AUTOMATION},
        "Into a self-hosted workflow.",
        "https://n8n.io",
        fields=(
            CredentialField(
                key="webhook_url", label="Webhook URL", secret=False,
                placeholder="https://n8n.example.com/webhook/…",
            ),
            _key("API key", help="Optional, if the workflow requires header auth."),
        ),
    ),
    _p(
        "zapier", "Zapier", {R.AUTOMATION},
        "6,000+ apps through a Zap.",
        "https://zapier.com/app/zaps",
        fields=(
            CredentialField(
                # Masked despite being a URL: a Catch Hook is a capability, not
                # an address. Anyone holding it can post into the Zap, so it is
                # a bearer credential wearing a URL's clothes.
                key="webhook_url", label="Catch Hook URL",
                placeholder="https://hooks.zapier.com/hooks/catch/…",
            ),
        ),
    ),
    _p(
        "gohighlevel", "GoHighLevel", {R.AUTOMATION},
        "Write back to a sub-account.",
        "https://marketplace.gohighlevel.com",
        fields=(
            _key("Private integration token"),
            CredentialField(key="location_id", label="Location ID", secret=False),
        ),
    ),
    _p(
        "slack", "Slack", {R.AUTOMATION},
        "Escalations into a channel.",
        "https://api.slack.com/apps",
        fields=(
            _key("Bot user OAuth token", ph="xoxb-…"),
            CredentialField(key="channel", label="Channel", secret=False, placeholder="#escalations"),
        ),
    ),
    _p(
        "hubspot", "HubSpot", {R.AUTOMATION},
        "Log calls on the contact record.",
        "https://app.hubspot.com/private-apps",
        fields=(_key("Private app token", ph="pat-…"),),
    ),
    _p(
        "salesforce", "Salesforce", {R.AUTOMATION},
        "Log calls on the record.",
        "https://help.salesforce.com",
        fields=(
            CredentialField(
                key="instance_url", label="Instance URL", secret=False,
                placeholder="https://your-org.my.salesforce.com",
            ),
            CredentialField(key="client_id", label="Consumer key", secret=False),
            CredentialField(key="client_secret", label="Consumer secret"),
        ),
    ),
)

_OBSERVABILITY: tuple[ProviderSpec, ...] = (
    _p(
        "langfuse", "Langfuse", {R.OBSERVABILITY},
        "Trace every model call.",
        "https://cloud.langfuse.com",
        fields=(
            CredentialField(key="public_key", label="Public key", secret=False, placeholder="pk-lf-…"),
            CredentialField(key="secret_key", label="Secret key", placeholder="sk-lf-…"),
            CredentialField(
                key="host", label="Host", secret=False, required=False,
                placeholder="https://cloud.langfuse.com",
            ),
        ),
    ),
)


PROVIDERS: tuple[ProviderSpec, ...] = (
    *_TELEPHONY,
    *_INTELLIGENCE,
    *_TRANSCRIBER,
    *_VOICE,
    *_STORAGE,
    *_AUTOMATION,
    *_OBSERVABILITY,
)

BY_ID: dict[str, ProviderSpec] = {p.id: p for p in PROVIDERS}
PROVIDER_IDS: frozenset[str] = frozenset(BY_ID)

# A provider appearing under two roles is deliberate (one Deepgram key does STT
# and TTS); a provider appearing twice in the tuple is a copy-paste bug that
# would silently shadow one of them in BY_ID.
assert len(BY_ID) == len(PROVIDERS), "duplicate provider id in PROVIDERS"


def spec(provider_id: str) -> ProviderSpec | None:
    return BY_ID.get(provider_id)


def for_role(role: ProviderRole) -> tuple[ProviderSpec, ...]:
    return tuple(p for p in PROVIDERS if role in p.roles)


def field_keys(provider_id: str) -> frozenset[str]:
    """What `connect_provider` will accept for this provider, and nothing else."""
    found = spec(provider_id)
    return frozenset(f.key for f in found.fields) if found else frozenset()


__all__ = [
    "BY_ID",
    "CALL_ROLES",
    "PROVIDERS",
    "PROVIDER_IDS",
    "ConnectMethod",
    "CredentialField",
    "ProviderRole",
    "ProviderSpec",
    "field_keys",
    "for_role",
    "spec",
]
