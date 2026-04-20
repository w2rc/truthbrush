from datetime import UTC

import pytest
from dateutil import parser as date_parse

from truthbrush.api import Api, LoginErrorException


@pytest.fixture(scope="module")
def api():
    return Api()


def as_datetime(date_str):
    """Datetime formatter function. Ensures timezone is UTC. Consider moving to Api class."""
    return date_parse.parse(date_str).replace(tzinfo=UTC)


def test_lookup(api):
    user = api.lookup(user_handle="realDonaldTrump")
    assert list(user.keys()) == [
        "id",
        "username",
        "acct",
        "display_name",
        "locked",
        "bot",
        "discoverable",
        "group",
        "created_at",
        "note",
        "url",
        "avatar",
        "avatar_static",
        "header",
        "header_static",
        "followers_count",
        "following_count",
        "statuses_count",
        "last_status_at",
        "verified",
        "location",
        "website",
        "accepting_messages",
        "chats_onboarded",
        "feeds_onboarded",
        "show_nonmember_group_statuses",
        "pleroma",
        "emojis",
        "fields",
    ]
    assert isinstance(user["id"], str)


def test_pull_statuses(api):
    username = "truthsocial"

    # COMPLETE PULLS

    # it fetches a timeline of the user's posts:
    full_timeline = list(api.pull_statuses(username=username, replies=False, verbose=True))
    assert len(full_timeline) > 25  # more than one page

    # the posts are in reverse chronological order:
    latest, earliest = full_timeline[0], full_timeline[-1]
    latest_at, earliest_at = as_datetime(latest["created_at"]), as_datetime(earliest["created_at"])
    assert earliest_at < latest_at

    # EMPTY PULLS

    # can use created_after param for filtering out posts:
    next_pull = list(
        api.pull_statuses(username=username, replies=False, created_after=latest_at, verbose=True)
    )
    assert not any(next_pull)

    # can use since_id param for filtering out posts:
    next_pull = list(
        api.pull_statuses(username=username, replies=False, since_id=latest["id"], verbose=True)
    )
    assert not any(next_pull)

    # PARTIAL PULLS

    n_posts = 50  # two and a half pages worth, to verify everything is ok
    recent = full_timeline[n_posts]
    recent_at = as_datetime(recent["created_at"])

    # can use created_after param for filtering out posts:
    partial_pull = list(
        api.pull_statuses(username=username, replies=False, created_after=recent_at, verbose=True)
    )
    assert len(partial_pull) == n_posts
    assert recent["id"] not in [post["id"] for post in partial_pull]

    # can use since_id param for filtering out posts:
    partial_pull = list(
        api.pull_statuses(username=username, replies=False, since_id=recent["id"], verbose=True)
    )
    assert len(partial_pull) == n_posts
    assert recent["id"] not in [post["id"] for post in partial_pull]

    # POST INFO
    # contains status info
    assert list(latest.keys()) == [
        "id",
        "created_at",
        "in_reply_to_id",
        "quote_id",
        "in_reply_to_account_id",
        "sensitive",
        "spoiler_text",
        "visibility",
        "language",
        "uri",
        "url",
        "content",
        "account",
        "media_attachments",
        "mentions",
        "tags",
        "card",
        "group",
        "quote",
        "in_reply_to",
        "reblog",
        "sponsored",
        "replies_count",
        "reblogs_count",
        "favourites_count",
        "favourited",
        "reblogged",
        "muted",
        "pinned",
        "bookmarked",
        "poll",
        "emojis",
        "_pulled",
    ]
    assert isinstance(latest["id"], str)


def test_get_auth_id_raises_login_error_exception(api):
    with pytest.raises(LoginErrorException):
        api.get_auth_id("invalid_username", "invalid_password")


def test_public_mode_does_not_require_credentials(monkeypatch):
    monkeypatch.delenv("TRUTHSOCIAL_USERNAME", raising=False)
    monkeypatch.delenv("TRUTHSOCIAL_PASSWORD", raising=False)
    monkeypatch.delenv("TRUTHSOCIAL_TOKEN", raising=False)
    public_api = Api(username=None, password=None, token=None, require_auth=False)
    assert public_api.auth_id is None
    # user_likes calls __check_login then short-circuits on top_num < 1 before any HTTP.
    assert list(public_api.user_likes("abc", top_num=0)) == []


def test_strict_mode_still_raises_without_credentials(monkeypatch):
    monkeypatch.delenv("TRUTHSOCIAL_USERNAME", raising=False)
    monkeypatch.delenv("TRUTHSOCIAL_PASSWORD", raising=False)
    monkeypatch.delenv("TRUTHSOCIAL_TOKEN", raising=False)
    strict_api = Api(username=None, password=None, token=None)
    with pytest.raises(LoginErrorException):
        strict_api.lookup(user_handle="realDonaldTrump")
