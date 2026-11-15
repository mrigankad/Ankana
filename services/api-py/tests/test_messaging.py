"""app.messaging with mocked HTTP only: request shapes, auth headers, error mapping,
retries, webhook signatures and parsing, STOP keywords, production guard. Nothing here
can reach a provider (every client uses httpx.MockTransport)."""

import base64
import hashlib
import hmac
import json
from urllib.parse import parse_qs

import httpx
import pytest

from app.messaging import (
    AcsEmailChannel,
    ChannelError,
    GupshupWhatsApp,
    Http,
    Message,
    MetaWhatsApp,
    Msg91Sms,
    OffChannel,
    TwilioSms,
    WaTemplates,
    assert_production_ready,
    build_channel,
    should_apply,
)
from app.messaging.inbound import is_opt_out
from app.messaging.sms import (
    parse_msg91_report,
    parse_twilio_webhook,
    twilio_signature,
    verify_twilio_signature,
)
from app.messaging.whatsapp import (
    fold,
    parse_gupshup_webhook,
    parse_meta_webhook,
    verify_meta_challenge,
    verify_meta_signature,
    verify_shared_token,
)


def http(handler, **kw) -> tuple[Http, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def wrapped(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return handler(req)

    return Http(httpx.Client(transport=httpx.MockTransport(wrapped)), sleep=lambda s: None,
                **kw), seen


TEMPLATES = WaTemplates({"remedy_due": {
    "en": {"name": "remedy_due_en", "language": "en", "id": "gs-uuid-en"},
    "hi": {"name": "remedy_due_hi", "language": "hi", "id": "gs-uuid-hi"}}})


# ------------------------------------------------------------------ Meta WhatsApp
def test_meta_template_message_shape_and_auth():
    h, seen = http(lambda r: httpx.Response(200, json={"messages": [{"id": "wamid.1"}]}))
    ch = MetaWhatsApp("TOKEN", "1234567890", templates=TEMPLATES, http=h)
    res = ch.send(Message("+91 98765 43210", "Day 1\nFeed crows", kind="remedy_due",
                          language="hi"))
    assert res.provider == "meta" and res.message_id == "wamid.1"
    req = seen[0]
    assert str(req.url) == "https://graph.facebook.com/v21.0/1234567890/messages"
    assert req.headers["authorization"] == "Bearer TOKEN"
    body = json.loads(req.content)
    assert body["messaging_product"] == "whatsapp" and body["to"] == "919876543210"
    assert body["type"] == "template"
    assert body["template"]["name"] == "remedy_due_hi"
    assert body["template"]["language"] == {"code": "hi"}
    assert body["template"]["components"] == [
        {"type": "body", "parameters": [{"type": "text", "text": "Day 1 | Feed crows"}]}]


def test_meta_session_message_and_unmapped_kind_send_text():
    h, seen = http(lambda r: httpx.Response(200, json={"messages": [{"id": "w"}]}))
    ch = MetaWhatsApp("T", "1", templates=TEMPLATES, http=h)
    ch.send(Message("919876543210", "hello", kind="remedy_due", session=True))
    ch.send(Message("919876543210", "hello", kind="other"))
    for req in seen:
        body = json.loads(req.content)
        assert body["type"] == "text" and body["text"]["body"] == "hello"


def test_meta_error_mapping_permanent_vs_retryable():
    def err(code, status=400):
        return http(lambda r: httpx.Response(status, json={"error": {"code": code,
                                                                     "message": "m"}}))[0]

    with pytest.raises(ChannelError) as e:
        MetaWhatsApp("T", "1", http=err(131047)).send(Message("919876543210", "x"))
    assert e.value.retryable is False and e.value.code == "131047"
    with pytest.raises(ChannelError) as e:
        MetaWhatsApp("T", "1", http=err(132001)).send(Message("919876543210", "x"))
    assert e.value.retryable is False
    with pytest.raises(ChannelError) as e:
        MetaWhatsApp("T", "1", http=err(131056)).send(Message("919876543210", "x"))
    assert e.value.retryable is True
    with pytest.raises(ChannelError) as e:  # 5xx without a body: retryable
        MetaWhatsApp("T", "1", http=http(lambda r: httpx.Response(500))[0], ).send(
            Message("919876543210", "x"))
    assert e.value.retryable is True


def test_retry_on_429_honours_retry_after_then_succeeds():
    calls = []
    sleeps = []

    def handler(req):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "3"})
        return httpx.Response(200, json={"messages": [{"id": "ok"}]})

    h = Http(httpx.Client(transport=httpx.MockTransport(handler)), sleep=sleeps.append)
    res = MetaWhatsApp("T", "1", http=h).send(Message("919876543210", "x"))
    assert res.message_id == "ok" and len(calls) == 2 and sleeps == [3.0]


def test_retries_are_bounded_and_connect_errors_retry_but_not_read_timeouts():
    n = {"c": 0}

    def down(req):
        n["c"] += 1
        raise httpx.ConnectError("no route", request=req)

    h = Http(httpx.Client(transport=httpx.MockTransport(down)), retries=2, sleep=lambda s: None)
    with pytest.raises(ChannelError):
        MetaWhatsApp("T", "1", http=h).send(Message("919876543210", "x"))
    assert n["c"] == 3

    n["c"] = 0

    def slow(req):
        n["c"] += 1
        raise httpx.ReadTimeout("slow", request=req)

    h = Http(httpx.Client(transport=httpx.MockTransport(slow)), sleep=lambda s: None)
    with pytest.raises(ChannelError):
        MetaWhatsApp("T", "1", http=h).send(Message("919876543210", "x"))
    assert n["c"] == 1  # a read timeout may have been accepted: never resend


def test_meta_webhook_signature_and_handshake():
    secret, raw = "app-secret", b'{"entry":[]}'
    good = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    assert verify_meta_signature(secret, raw, good)
    assert not verify_meta_signature(secret, raw + b" ", good)  # body tampered
    assert not verify_meta_signature("other", raw, good)
    assert not verify_meta_signature(secret, raw, None)
    assert not verify_meta_signature(secret, raw, good.replace("sha256=", "sha1="))
    assert not verify_meta_signature("", raw, good)  # unconfigured secret never passes
    assert verify_meta_challenge("vt", "subscribe", "vt", "42") == "42"
    assert verify_meta_challenge("vt", "subscribe", "bad", "42") is None
    assert verify_meta_challenge("", "subscribe", "", "42") is None


def test_meta_webhook_parsing_statuses_and_replies():
    payload = {"entry": [{"changes": [{"value": {
        "statuses": [
            {"id": "wamid.1", "status": "delivered"},
            {"id": "wamid.2", "status": "read"},
            {"id": "wamid.3", "status": "failed",
             "errors": [{"code": 131026, "title": "Undeliverable"}]},
            {"id": "wamid.4", "status": "deleted"}],
        "messages": [{"from": "919876543210", "type": "text", "text": {"body": "STOP"}},
                     {"from": "919876543211", "type": "button", "button": {"text": "Stop"}}]}}]}]}
    st, inbound = parse_meta_webhook(payload)
    assert [(s.message_id, s.status) for s in st] == [
        ("wamid.1", "delivered"), ("wamid.2", "read"), ("wamid.3", "failed")]
    assert st[2].error == "131026 Undeliverable"
    assert [(i.sender, i.text) for i in inbound] == [("919876543210", "STOP"),
                                                     ("919876543211", "Stop")]


# --------------------------------------------------------------------- Gupshup
def test_gupshup_template_and_session_shapes():
    h, seen = http(lambda r: httpx.Response(200, json={"status": "submitted",
                                                       "messageId": "gs-1"}))
    ch = GupshupWhatsApp("KEY", "919000000000", "WayamApp", templates=TEMPLATES, http=h)
    assert ch.send(Message("9876543210", "Day 1", kind="remedy_due")).message_id == "gs-1"
    ch.send(Message("9876543210", "hi", kind="remedy_due", session=True))
    tpl, sess = seen
    assert tpl.url.path == "/wa/api/v1/template/msg" and tpl.headers["apikey"] == "KEY"
    form = parse_qs(tpl.content.decode())
    assert form["channel"] == ["whatsapp"] and form["destination"] == ["919876543210"]
    assert form["src.name"] == ["WayamApp"] and form["source"] == ["919000000000"]
    assert json.loads(form["template"][0]) == {"id": "gs-uuid-en", "params": ["Day 1"]}
    assert sess.url.path == "/wa/api/v1/msg"
    assert json.loads(parse_qs(sess.content.decode())["message"][0]) == {
        "type": "text", "text": "hi"}


def test_gupshup_errors():
    ch = GupshupWhatsApp("K", "919000000000", "A", http=http(
        lambda r: httpx.Response(200, json={"status": "error", "message": "bad"}))[0])
    with pytest.raises(ChannelError) as e:
        ch.send(Message("9876543210", "x"))
    assert e.value.retryable is False
    ch = GupshupWhatsApp("K", "919000000000", "A", http=http(lambda r: httpx.Response(503))[0],
                         )
    with pytest.raises(ChannelError) as e:
        ch.send(Message("9876543210", "x"))
    assert e.value.retryable is True


def test_gupshup_webhook_parsing_and_token():
    st, _ = parse_gupshup_webhook({"type": "message-event", "payload": {
        "id": "wa-1", "gsId": "gs-1", "type": "delivered", "destination": "91"}})
    assert {s.message_id for s in st} == {"wa-1", "gs-1"} and st[0].status == "delivered"
    _, inbound = parse_gupshup_webhook({"type": "message", "payload": {
        "source": "919876543210", "type": "text", "payload": {"text": "stop"}}})
    assert inbound[0].sender == "919876543210" and inbound[0].text == "stop"
    assert parse_gupshup_webhook({"type": "message-event", "payload": {
        "id": "x", "type": "enqueued"}}) == ([], [])
    assert verify_shared_token("tok", "tok") and not verify_shared_token("tok", "no")
    assert not verify_shared_token("", "") and not verify_shared_token("tok", None)


# ------------------------------------------------------------------------ MSG91
def test_msg91_request_has_sender_and_dlt_template():
    h, seen = http(lambda r: httpx.Response(200, json={"type": "success", "message": "req-9"}))
    ch = Msg91Sms("AUTHKEY", "WAYAMX", default_template_id="DLT-DEFAULT",
                  templates={"otp": "DLT-OTP"}, http=h)
    assert ch.send(Message("98765 43210", "Your code is 123456", kind="otp")).message_id == "req-9"
    ch.send(Message("+919876543210", "Reminder", kind="remedy_due"))
    otp, rem = seen
    assert otp.headers["authkey"] == "AUTHKEY"
    body = json.loads(otp.content)
    assert body == {"sender": "WAYAMX", "route": "4", "country": "91", "DLT_TE_ID": "DLT-OTP",
                    "sms": [{"message": "Your code is 123456", "to": ["919876543210"]}]}
    assert json.loads(rem.content)["DLT_TE_ID"] == "DLT-DEFAULT"


def test_msg91_errors_and_missing_template():
    ch = Msg91Sms("K", "WAYAMX", http=http(lambda r: httpx.Response(200, json={"type": "success"
                                                                               }))[0])
    with pytest.raises(ChannelError) as e:  # no DLT template id: refuse before any request
        ch.send(Message("9876543210", "x", kind="remedy_due"))
    assert e.value.retryable is False
    ch = Msg91Sms("K", "S", default_template_id="T", http=http(
        lambda r: httpx.Response(200, json={"type": "error", "message": "IP blocked"}))[0])
    with pytest.raises(ChannelError) as e:  # HTTP 200 with type=error is a failure
        ch.send(Message("9876543210", "x"))
    assert e.value.retryable is False
    ch = Msg91Sms("K", "S", default_template_id="T", http=http(lambda r: httpx.Response(502))[0])
    with pytest.raises(ChannelError):
        ch.send(Message("9876543210", "x"))
    with pytest.raises(RuntimeError):
        Msg91Sms("", "S")


def test_msg91_report_parsing():
    st = parse_msg91_report([{"requestId": "r1", "report": [
        {"number": "91", "status": "1", "desc": "DELIVERED"},
        {"number": "91", "status": "2", "desc": "FAILED"},
        {"number": "91", "status": "99", "desc": "MYSTERY"}]}, "junk", {"report": []}])
    assert [(s.message_id, s.status) for s in st] == [("r1", "delivered"), ("r1", "failed")]


# ----------------------------------------------------------------------- Twilio
def test_twilio_request_shape_basic_auth_and_errors():
    h, seen = http(lambda r: httpx.Response(201, json={"sid": "SM1", "status": "queued"}))
    ch = TwilioSms("ACxxx", "tok", from_number="+15005550006",
                   status_callback="https://api.example.test/v1/webhooks/sms/twilio", http=h)
    assert ch.send(Message("9876543210", "hi")).message_id == "SM1"
    req = seen[0]
    assert str(req.url) == "https://api.twilio.com/2010-04-01/Accounts/ACxxx/Messages.json"
    assert req.headers["authorization"] == "Basic " + base64.b64encode(b"ACxxx:tok").decode()
    form = parse_qs(req.content.decode())
    assert form["To"] == ["+919876543210"] and form["From"] == ["+15005550006"]
    assert form["Body"] == ["hi"] and "StatusCallback" in form
    ms = TwilioSms("ACxxx", "tok", messaging_service_sid="MG1", http=h)
    ms.send(Message("9876543210", "hi"))
    form = parse_qs(seen[1].content.decode())
    assert form["MessagingServiceSid"] == ["MG1"] and "From" not in form

    bad = TwilioSms("A", "t", from_number="+1", http=http(lambda r: httpx.Response(
        400, json={"code": 21211, "message": "Invalid 'To'"}))[0])
    with pytest.raises(ChannelError) as e:
        bad.send(Message("1", "x"))
    assert e.value.retryable is False and e.value.code == "21211"
    down = TwilioSms("A", "t", from_number="+1", http=http(lambda r: httpx.Response(500))[0])
    with pytest.raises(ChannelError) as e:
        down.send(Message("9876543210", "x"))
    assert e.value.retryable is True
    with pytest.raises(RuntimeError):
        TwilioSms("A", "t")


def test_twilio_signature_known_vector_and_verification():
    # Worked example from Twilio's security documentation.
    url = "https://mycompany.com/myapp.php?foo=1&bar=2"
    params = {"CallSid": "CA1234567890ABCDE", "Caller": "+14158675310", "Digits": "1234",
              "From": "+14158675310", "To": "+18005551212"}
    sig = twilio_signature("12345", url, params)
    assert sig == "GvWf1cFY/Q7PnoempGyD5oXAezc="
    assert verify_twilio_signature("12345", url, params, sig)
    assert not verify_twilio_signature("12345", url, {**params, "Digits": "9"}, sig)
    assert not verify_twilio_signature("12345", url + "x", params, sig)
    assert not verify_twilio_signature("", url, params, sig)
    assert not verify_twilio_signature("12345", url, params, None)


def test_twilio_webhook_parsing():
    st, inbound = parse_twilio_webhook({"MessageSid": "SM1", "MessageStatus": "undelivered",
                                        "ErrorCode": "30003"})
    assert st[0].status == "failed" and st[0].error == "twilio 30003" and not inbound
    st, _ = parse_twilio_webhook({"MessageSid": "SM1", "MessageStatus": "delivered"})
    assert st[0].status == "delivered"
    st, inbound = parse_twilio_webhook({"From": "+919876543210", "Body": "STOP"})
    assert not st and inbound[0].sender == "+919876543210"


# ------------------------------------------------------------------------- email
def test_acs_rest_request_is_hmac_signed_and_errors_map():
    key = base64.b64encode(b"secret-key").decode()
    conn = f"endpoint=https://acs.example.test/;accesskey={key}"
    h, seen = http(lambda r: httpx.Response(202, json={"id": "op-1"}))
    ch = AcsEmailChannel(conn, "Ankana <no-reply@example.test>", http=h)
    res = ch.send(Message("a@example.test", "Body", "Subj", html="<b>x</b>",
                          unsubscribe_url="https://x/stop"))
    assert res.message_id == "op-1"
    req = seen[0]
    assert req.url.path == "/emails:send" and req.url.params["api-version"] == "2023-03-31"
    assert req.headers["authorization"].startswith("HMAC-SHA256 SignedHeaders=x-ms-date;host;")
    body = json.loads(req.content)
    assert body["senderAddress"] == "no-reply@example.test"
    assert body["content"] == {"subject": "Subj", "plainText": "Body", "html": "<b>x</b>"}
    assert body["headers"] == {"List-Unsubscribe": "<https://x/stop>"}
    assert req.headers["x-ms-content-sha256"] == base64.b64encode(
        hashlib.sha256(req.content).digest()).decode()
    bad = AcsEmailChannel(conn, "n@example.test", http=http(lambda r: httpx.Response(401))[0])
    with pytest.raises(ChannelError) as e:
        bad.send(Message("a@example.test", "b", "s"))
    assert e.value.retryable is False
    with pytest.raises(RuntimeError):
        AcsEmailChannel("nonsense", "n@example.test")


def test_acs_sdk_missing_is_a_clean_permanent_error():
    key = base64.b64encode(b"k").decode()
    ch = AcsEmailChannel(f"endpoint=https://a.test/;accesskey={key}", "n@example.test",
                         use_sdk=True)
    try:
        import azure.communication.email  # noqa: F401
    except ImportError:
        with pytest.raises(ChannelError) as e:
            ch.send(Message("a@example.test", "b", "s"))
        assert e.value.retryable is False


# --------------------------------------------------------- factory and production
ENV = {
    "WHATSAPP_CLOUD_TOKEN": "t", "WHATSAPP_PHONE_NUMBER_ID": "1",
    "MSG91_AUTH_KEY": "k", "MSG91_SENDER_ID": "WAYAMX", "MSG91_DLT_TEMPLATE_ID": "d",
    "TWILIO_ACCOUNT_SID": "AC1", "TWILIO_AUTH_TOKEN": "tok", "TWILIO_FROM": "+1",
    "GUPSHUP_API_KEY": "k", "GUPSHUP_SOURCE": "91", "GUPSHUP_APP_NAME": "A",
}


def test_factory_builds_each_backend_and_reports_missing_settings():
    assert build_channel("whatsapp", "meta", ENV).name == "meta"
    assert build_channel("whatsapp", "gupshup", ENV).name == "gupshup"
    assert build_channel("sms", "msg91", ENV).name == "msg91"
    assert build_channel("sms", "twilio", ENV).name == "twilio"
    assert build_channel("sms", "off", {}).name == "off"
    with pytest.raises(RuntimeError, match="WHATSAPP_CLOUD_TOKEN"):
        build_channel("whatsapp", "meta", {})
    with pytest.raises(RuntimeError, match="MSG91_SENDER_ID"):
        build_channel("sms", "msg91", {"MSG91_AUTH_KEY": "k"})
    with pytest.raises(RuntimeError, match="unsupported"):
        build_channel("sms", "carrier-pigeon", {})
    with pytest.raises(RuntimeError, match="WHATSAPP_TEMPLATES"):
        build_channel("whatsapp", "meta", {**ENV, "WHATSAPP_TEMPLATES": "{nope"})
    with pytest.raises(ChannelError) as e:
        OffChannel("sms").send(Message("1", "x"))
    assert e.value.retryable is False


def test_production_refuses_console_for_sms_and_whatsapp(monkeypatch):
    for kind in ("sms", "whatsapp"):
        with pytest.raises(RuntimeError, match="not allowed in production"):
            build_channel(kind, "console", {}, production=True)
        assert build_channel(kind, "console", {}, production=False).name == "console"
    # email console is the auth/notify default and is not changed by this guard
    assert build_channel("email", "console", {}, production=True).name == "console"
    monkeypatch.setenv("API_ENV", "production")
    from app.notify import channels

    monkeypatch.delenv("NOTIFY_SMS_BACKEND", raising=False)
    with pytest.raises(RuntimeError, match="not allowed in production"):
        channels.get_channel("sms")
    with pytest.raises(RuntimeError):
        assert_production_ready({})
    assert_production_ready({"NOTIFY_SMS_BACKEND": "off", "NOTIFY_WHATSAPP_BACKEND": "off"})
    assert_production_ready({"NOTIFY_SMS_BACKEND": "msg91", "NOTIFY_WHATSAPP_BACKEND": "meta",
                             **ENV})


def test_auth_sms_adapters_and_production_guard():
    import dataclasses

    from app.auth.config import AuthConfig
    from app.auth.mailer import build_sms

    cfg = AuthConfig()
    prod = dataclasses.replace(cfg, env="production", sms="console")
    assert type(build_sms(prod)).__name__ == "NoSms"  # unchanged: phone codes just off
    with pytest.raises(RuntimeError, match="MSG91_AUTH_KEY"):
        build_sms(dataclasses.replace(cfg, sms="msg91"))
    with pytest.raises(RuntimeError, match="unknown AUTH_SMS"):
        build_sms(dataclasses.replace(cfg, sms="pigeon"))


# ------------------------------------------------------------------ status & STOP
def test_status_only_moves_forward():
    assert should_apply(None, "sent") and should_apply("sent", "delivered")
    assert should_apply("delivered", "read") and not should_apply("read", "delivered")
    assert not should_apply("delivered", "delivered") and not should_apply("delivered", "sent")
    assert should_apply("sent", "failed") and should_apply(None, "failed")
    assert not should_apply("delivered", "failed") and not should_apply("read", "failed")


@pytest.mark.parametrize("word", ["STOP", "stop", " Stop. ", "UNSUBSCRIBE", "Cancel", "stop!",
                                  "बंद", "बंद करें", "opt out"])
def test_opt_out_keywords(word):
    assert is_opt_out(word)


@pytest.mark.parametrize("word", ["thanks", "please stop by tomorrow", "", "start", "yes"])
def test_non_opt_out_text(word):
    assert not is_opt_out(word)


def test_fold_template_parameters():
    assert fold("a\n\nb\tc   d") == "a | b c d"


def test_whatsapp_template_fallback_to_english():
    assert TEMPLATES.get("remedy_due", "ta").name == "remedy_due_en"
    assert TEMPLATES.get("missing", "en") is None
