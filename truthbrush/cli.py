"""Defines the CLI for Truthbrush."""

import datetime
import json

import click

from .api import Api


@click.group()
@click.option(
    "--no-auth",
    is_flag=True,
    default=False,
    help="Run without authentication. Only public endpoints will succeed.",
)
@click.pass_context
def cli(ctx: click.Context, no_auth: bool):
    """This is an API client for Truth Social."""
    ctx.ensure_object(dict)
    ctx.obj["api"] = Api(require_auth=not no_auth)


@cli.command()
@click.argument("group_id")
@click.option("--limit", default=20, help="Limit the number of items returned", type=int)
@click.pass_context
def groupposts(ctx: click.Context, group_id: str, limit: int):
    """Pull posts from group timeline"""
    print(json.dumps(ctx.obj["api"].group_posts(group_id, limit)))


@cli.command()
@click.pass_context
def trends(ctx: click.Context):
    """Pull trendy Truths."""
    print(json.dumps(ctx.obj["api"].trending()))


@cli.command()
@click.pass_context
def tags(ctx: click.Context):
    """Pull trendy tags."""
    print(json.dumps(ctx.obj["api"].tags()))


@cli.command()
@click.pass_context
def grouptags(ctx: click.Context):
    """Pull group tags."""
    print(json.dumps(ctx.obj["api"].group_tags()))


@cli.command()
@click.pass_context
def grouptrends(ctx: click.Context):
    """Pull group trends."""
    print(json.dumps(ctx.obj["api"].trending_groups()))


@cli.command()
@click.pass_context
def groupsuggest(ctx: click.Context):
    """Pull group suggestions."""
    print(json.dumps(ctx.obj["api"].suggested_groups()))


@cli.command()
@click.argument("handle")
@click.pass_context
def user(ctx: click.Context, handle: str):
    """Pull a user's metadata."""
    print(json.dumps(ctx.obj["api"].lookup(handle)))


@cli.command()
@click.argument("query")
@click.option(
    "--searchtype",
    help="Type of search query (accounts, statuses, groups, or hashtags)",
    type=click.Choice(["accounts", "statuses", "hashtags", "groups"]),
)
@click.option("--limit", default=40, help="Limit the number of items returned", type=int)
@click.option("--resolve", help="Resolve", type=bool)
@click.option(
    "--start-date", default=None, help="Start date for search results (e.g. 2026-01-01)", type=str
)
@click.option(
    "--end-date", default=None, help="End date for search results (e.g. 2026-03-01)", type=str
)
@click.pass_context
def search(
    ctx: click.Context,
    searchtype: str,
    query: str,
    limit: int,
    resolve: bool,
    start_date: str,
    end_date: str,
):
    """Search for users, statuses, groups, or hashtags."""
    for page in ctx.obj["api"].search(
        searchtype, query, limit, resolve, start_date=start_date, end_date=end_date
    ):
        print(json.dumps(page[searchtype]))


@cli.command()
@click.pass_context
def suggestions(ctx: click.Context):
    """Pull the list of suggested users."""
    print(json.dumps(ctx.obj["api"].suggested()))


@cli.command()
@click.pass_context
def ads(ctx: click.Context):
    """Pull ads."""
    print(json.dumps(ctx.obj["api"].ads()))


# @cli.command()
# @click.argument("handle")
# @click.option("--maximum", help="the maximum number of followers to pull", type=int)
# @click.option(
#     "--resume",
#     help="the `max_id` cursor to resume from, if necessary (pull this from logs to resume a failed/stalled export)",
#     type=str,
# )
# def followers(handle: str, maximum: int = None, resume: str = None):
#     """Pull a user's followers."""

#     for follower in api.user_followers(handle, maximum=maximum, resume=resume):
#         print(json.dumps(follower))


# @cli.command()
# @click.argument("handle")
# @click.option(
#     "--maximum", help="the maximum number of followed users to pull", type=int
# )
# @click.option(
#     "--resume",
#     help="the `max_id` cursor to resume from, if necessary (pull this from logs to resume a failed/stalled export)",
#     type=str,
# )
# def following(handle: str, maximum: int = None, resume: str = None):
#     """Pull users a given user follows."""

#     for followed in api.user_following(handle, maximum=maximum, resume=resume):
#         print(json.dumps(followed))


@cli.command()
@click.argument("username")
@click.option(
    "--replies/--no-replies",
    default=False,
    help="Include replies when pulling posts (defaults to no replies)",
)
@click.option(
    "--created-after",
    default=None,
    help="Only pull posts created on or after the specified datetime, e.g. 2021-10-02 or 2011-11-04T00:05:23+04:00 (defaults to none). If a timezone is not specified, UTC is assumed.",
    type=datetime.datetime.fromisoformat,
)
@click.option(
    "--created-before",
    default=None,
    help="Only pull posts created on or before the specified datetime, e.g. 2021-10-02 or 2011-11-04T00:05:23+04:00 (defaults to none). If a timezone is not specified, UTC is assumed.",
    type=datetime.datetime.fromisoformat,
)
@click.option("--pinned/--all", default=False, help="Only pull pinned posts (defaults to all)")
@click.pass_context
def statuses(
    ctx: click.Context,
    username: str,
    replies: bool = False,
    created_after: datetime.datetime | None = None,
    created_before: datetime.datetime | None = None,
    pinned: bool = False,
):
    """Pull a user's statuses"""
    # Assume UTC if no timezone is specified
    if created_after is not None and created_after.tzinfo is None:
        created_after = created_after.replace(tzinfo=datetime.UTC)
    if created_before is not None and created_before.tzinfo is None:
        created_before = created_before.replace(tzinfo=datetime.UTC)

    for page in ctx.obj["api"].pull_statuses(
        username,
        created_after=created_after,
        created_before=created_before,
        replies=replies,
        pinned=pinned,
    ):
        print(json.dumps(page))


@cli.command()
@click.argument("post")
@click.option("--includeall", is_flag=True, help="return all comments on post.")
@click.argument("top_num")
@click.pass_context
def likes(ctx: click.Context, post: str, includeall: bool, top_num: int):
    """Pull the top_num most recent users who liked the post."""
    for page in ctx.obj["api"].user_likes(post, includeall, top_num):
        print(json.dumps(page))


@cli.command()
@click.argument("post")
@click.option("--includeall", is_flag=True, help="return all comments on post. Overrides top_num.")
@click.option("--onlyfirst", is_flag=True, help="return only direct replies to specified post")
@click.argument("top_num")
@click.pass_context
def comments(ctx: click.Context, post: str, includeall: bool, onlyfirst: bool, top_num: int = 40):
    """Pull the top_num comments on a post (defaults to all users, including replies)."""
    for page in ctx.obj["api"].pull_comments(post, includeall, onlyfirst, top_num):
        print(page)
