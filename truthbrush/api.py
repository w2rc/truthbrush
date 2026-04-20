import json
import logging
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from time import sleep
from typing import Any, Literal, cast

import curl_cffi
from curl_cffi import requests
from dateutil import parser as date_parse
from dotenv import load_dotenv
from loguru import logger

load_dotenv()  # take environment variables from .env.

_DEBUG_ENV = os.getenv("DEBUG") or ""
logging.basicConfig(
    level=logging.DEBUG if _DEBUG_ENV.lower() not in ("", "false") else logging.INFO
)

BASE_URL = "https://truthsocial.com"
API_BASE_URL = "https://truthsocial.com/api"
USER_AGENT: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
IMPERSONATE_TARGET: str = "chrome146"

# Oauth client credentials, from https://truthsocial.com/packs/js/application-d77ef3e9148ad1d0624c.js
CLIENT_ID = "9X1Fdd-pxNsAgEDNi_SfhJWi8T-vLuV2WVzKIbkTCw4"
CLIENT_SECRET = "ozF8jzI4968oTKFkEnsBC-UbLPCdrSv0MkXGQu2o_-M"

proxies = {"http": os.getenv("http_proxy"), "https": os.getenv("https_proxy")}

TRUTHSOCIAL_USERNAME = os.getenv("TRUTHSOCIAL_USERNAME")
TRUTHSOCIAL_PASSWORD = os.getenv("TRUTHSOCIAL_PASSWORD")

TRUTHSOCIAL_TOKEN = os.getenv("TRUTHSOCIAL_TOKEN")


class LoginErrorException(Exception):
    pass


class GeoblockException(LoginErrorException):
    """Raised when Truth Social blocks access due to geographic restrictions"""

    pass


class CFBlockException(LoginErrorException):
    """Raised when Cloudflare blocks the request"""

    pass


def date_to_bound(dt_input: str | datetime, bound: Literal["start", "end"]) -> int:
    if isinstance(dt_input, str):
        dt_input = datetime.fromisoformat(dt_input)
        if dt_input.hour or dt_input.minute or dt_input.second or dt_input.microsecond:
            raise ValueError(
                "date string must not include a time component. Pass in datetime object for time-specific bounds."
            )

    if dt_input.tzinfo is None:
        dt_input = dt_input.replace(tzinfo=UTC)

    if bound == "start":
        dt = dt_input.replace(hour=0, minute=0, second=0, microsecond=0)
        ms = int(dt.timestamp() * 1000)
        return (ms << 16) | 0x0000
    else:
        dt = dt_input.replace(hour=23, minute=59, second=59, microsecond=999999)
        ms = int(dt.timestamp() * 1000)
        return (ms << 16) | 0xFFFF


class Api:
    def __init__(
        self,
        username: str | None = TRUTHSOCIAL_USERNAME,
        password: str | None = TRUTHSOCIAL_PASSWORD,
        token: str | None = TRUTHSOCIAL_TOKEN,
        *,
        require_auth: bool = True,
    ):
        self.ratelimit_max = 300
        self.ratelimit_remaining: int | None = None
        self.ratelimit_reset: datetime | None = None
        self.__username = username
        self.__password = password
        self.auth_id = token
        self.require_auth = require_auth

    def __check_login(self):
        """Runs before any login-walled function to check for login credentials and generates an auth ID token"""
        if self.auth_id is None:
            if not self.require_auth:
                return
            if self.__username is None:
                raise LoginErrorException("Username is missing.")
            if self.__password is None:
                raise LoginErrorException("Password is missing.")
            self.auth_id = self.get_auth_id(self.__username, self.__password)
            logger.warning(f"Using token {self.auth_id}")

    def _make_session(self):
        s = requests.Session()
        return s

    def _check_ratelimit(self, resp):
        if resp.headers.get("x-ratelimit-limit") is not None:
            self.ratelimit_max = int(resp.headers.get("x-ratelimit-limit"))
        if resp.headers.get("x-ratelimit-remaining") is not None:
            self.ratelimit_remaining = int(resp.headers.get("x-ratelimit-remaining"))
        if resp.headers.get("x-ratelimit-reset") is not None:
            self.ratelimit_reset = date_parse.parse(resp.headers.get("x-ratelimit-reset"))

        if (
            self.ratelimit_remaining is not None
            and self.ratelimit_remaining <= 50
            and self.ratelimit_reset is not None
        ):  # We do 50 to be safe; their tracking is a bit stochastic... it can jump down quickly
            now = datetime.now(UTC)
            time_to_sleep = (
                self.ratelimit_reset.replace(tzinfo=UTC) - now
            ).total_seconds()
            logger.warning(f"Approaching rate limit; sleeping for {time_to_sleep} seconds...")
            if time_to_sleep > 0:
                sleep(time_to_sleep)
            else:
                sleep(10)

    def _get(self, url: str, params: dict | None = None) -> Any:
        headers = {"User-Agent": USER_AGENT}
        if self.auth_id is not None:
            headers["Authorization"] = "Bearer " + self.auth_id
        try:
            resp = self._make_session().get(
                API_BASE_URL + url,
                params=params,
                proxies=proxies,
                impersonate=IMPERSONATE_TARGET,
                headers=headers,
            )
        except curl_cffi.curl.CurlError as e:
            logger.error(f"Curl error: {e}")
            return None

        # Will also sleep
        self._check_ratelimit(resp)

        try:
            r = resp.json()
        except json.JSONDecodeError:
            body = resp.text
            if "Just a moment" in body or "cdn-cgi/challenge-platform" in body:
                raise CFBlockException(
                    "Cloudflare challenge page received instead of JSON. "
                    "Source IP is likely flagged; try a different network."
                ) from None
            logger.error(f"Failed to decode JSON: {body}")
            r = None

        return r

    def _get_paginated(
        self, url: str, params: dict | None = None, resume: str | None = None
    ) -> Any:
        next_link: str | None = API_BASE_URL + url
        headers = {"User-Agent": USER_AGENT}
        if self.auth_id is not None:
            headers["Authorization"] = "Bearer " + self.auth_id

        if resume is not None:
            next_link += f"?max_id={resume}"

        while next_link is not None:
            resp = self._make_session().get(
                next_link,
                params=params,
                proxies=proxies,
                impersonate=IMPERSONATE_TARGET,
                headers=headers,
            )
            link_header = resp.headers.get("Link", "")
            next_link = None
            for link in link_header.split(","):
                parts = link.split(";")
                if len(parts) == 2 and parts[1].strip() == 'rel="next"':
                    next_link = parts[0].strip("<>")
                    break
            logger.info(f"Next: {next_link}, resp: {resp}, headers: {resp.headers}")
            yield resp.json()

            # Will also sleep
            self._check_ratelimit(resp)

    def user_likes(self, post: str, include_all: bool = False, top_num: int = 40) -> Iterator[dict]:
        """Return the top_num most recent (or all) users who liked the post."""
        self.__check_login()
        top_num = int(top_num)
        if top_num < 1:
            return
        post = post.split("/")[-1]
        n_output = 0
        for followers_batch in self._get_paginated(
            f"/v1/statuses/{post}/favourited_by", resume=None, params=dict(limit=80)
        ):
            for f in followers_batch:
                yield f
                n_output += 1
                if not include_all and n_output >= top_num:
                    return

    def pull_comments(
        self,
        post: str,
        include_all: bool = False,
        only_first: bool = False,
        top_num: int = 40,
    ) -> Iterator[dict]:
        """Return the top_num oldest (or all) replies to a post."""
        self.__check_login()
        top_num = int(top_num)
        if top_num < 1:
            return
        post = post.split("/")[-1]
        n_output = 0
        for followers_batch in self._get_paginated(
            f"/v1/statuses/{post}/context/descendants",
            resume=None,
            params=dict(sort="oldest"),
        ):
            # TO-DO: sort by sort=controversial, sort=newest, sort=oldest, sort=trending
            for f in followers_batch:
                if (only_first and f["in_reply_to_id"] == post) or not only_first:
                    yield f
                    n_output += 1
                    if not include_all and n_output >= top_num:
                        return

    def lookup(self, user_handle: str | None = None) -> dict | None:
        """Lookup a user's information."""

        self.__check_login()
        assert user_handle is not None
        return self._get("/v1/accounts/lookup", params=dict(acct=user_handle))

    def search(
        self,
        searchtype: str | None = None,
        query: str | None = None,
        limit: int = 40,
        resolve: bool = True,
        offset: int = 0,
        min_id: str = "0",
        max_id: str | None = None,
        start_date: str | datetime | None = None,
        end_date: str | datetime | None = None,
    ) -> Iterator[dict]:
        """Search users, statuses or hashtags."""

        self.__check_login()
        assert query is not None and searchtype is not None

        # error handling for date and id bounds
        if min_id != "0" and start_date is not None:
            raise ValueError("Cannot specify both min_id and start_date")
        if max_id is not None and end_date is not None:
            raise ValueError("Cannot specify both max_id and end_date")

        if start_date is not None:
            min_id = str(date_to_bound(start_date, "start"))
        if end_date is not None:
            max_id = str(date_to_bound(end_date, "end"))
        if max_id is not None:
            assert min_id < max_id, "min_id must be less than max_id"

        PAGE_SIZE = 40
        total_yielded = 0
        while total_yielded < limit:
            fetch_size = min(PAGE_SIZE, limit - total_yielded)
            params = dict(
                q=query,
                resolve=resolve,
                limit=fetch_size,
                type=searchtype,
                offset=offset,
                min_id=min_id,
            )
            if max_id is not None:
                params["max_id"] = max_id

            resp = self._get("/v2/search", params=params)

            if not resp or all(value == [] for value in resp.values()):
                break

            yield resp
            total_yielded += sum(len(v) for v in resp.values() if isinstance(v, list))
            offset += PAGE_SIZE

    def hashtag(
        self,
        tag: str | None = None,
        limit: int = 100,
    ) -> Iterator[list[dict]]:
        """Collect posts with a specific hashtag."""

        self.__check_login()
        assert tag is not None
        if tag.startswith("#"):
            # Remove the hashtag symbol
            tag = tag[1:]

        num_results = 0
        params: dict = dict()
        while num_results < limit:
            logger.info(f"Collecting posts with hashtag: {tag}, max_id: {params.get('max_id')}")
            resp = self._get(
                f"/v1/timelines/tag/{tag}",
                params=params,
            )

            if not resp:
                break

            # Filter out empty results
            results = [value for value in resp if value]
            if not results:
                break

            num_results += len(results)
            params["max_id"] = results[-1]["id"]

            yield results

    def trending(self, limit=10):
        """Return trending truths.
        Optional arg limit<20 specifies number to return."""

        self.__check_login()
        return self._get(f"/v1/truth/trending/truths?limit={limit}")

    def group_posts(self, group_id: str, limit: int = 20) -> list[dict]:
        self.__check_login()
        timeline: list[dict] = []
        posts = self._get(f"/v1/timelines/group/{group_id}?limit={limit}")
        while posts:
            timeline += posts
            limit = limit - len(posts)
            if limit <= 0:
                break
            max_id = posts[-1]["id"]
            posts = self._get(f"/v1/timelines/group/{group_id}?max_id={max_id}&limit={limit}")
        return timeline

    def tags(self):
        """Return trending tags."""

        self.__check_login()
        return self._get("/v1/trends")

    def suggested(self, maximum: int = 50) -> Any:
        """Return a list of suggested users to follow."""
        self.__check_login()
        return self._get(f"/v2/suggestions?limit={maximum}")

    def trending_groups(self, limit=10):
        """Return trending group truths.
        Optional arg limit<20 specifies number to return."""

        self.__check_login()
        return self._get(f"/v1/truth/trends/groups?limit={limit}")

    def group_tags(self):
        """Return trending group tags."""

        self.__check_login()
        return self._get("/v1/groups/tags")

    def suggested_groups(self, maximum: int = 50) -> Any:
        """Return a list of suggested groups to follow."""
        self.__check_login()
        return self._get(f"/v1/truth/suggestions/groups?limit={maximum}")

    def ads(self, device: str = "desktop") -> Any:
        """Return a list of ads from Rumble's Ad Platform via Truth Social API."""

        self.__check_login()
        return self._get(f"/v3/truth/ads?device={device}")

    def user_followers(
        self,
        user_handle: str | None = None,
        user_id: str | None = None,
        maximum: int = 1000,
        resume: str | None = None,
    ) -> Iterator[dict]:
        assert user_handle is not None or user_id is not None
        if user_id is None:
            user = self.lookup(user_handle)
            assert user is not None, "lookup returned no user"
            user_id = user["id"]

        n_output = 0
        for followers_batch in self._get_paginated(
            f"/v1/accounts/{user_id}/followers", resume=resume
        ):
            for f in followers_batch:
                yield f
                n_output += 1
                if maximum is not None and n_output >= maximum:
                    return

    def user_following(
        self,
        user_handle: str | None = None,
        user_id: str | None = None,
        maximum: int = 1000,
        resume: str | None = None,
    ) -> Iterator[dict]:
        assert user_handle is not None or user_id is not None
        if user_id is None:
            user = self.lookup(user_handle)
            assert user is not None, "lookup returned no user"
            user_id = user["id"]

        n_output = 0
        for followers_batch in self._get_paginated(
            f"/v1/accounts/{user_id}/following", resume=resume
        ):
            for f in followers_batch:
                yield f
                n_output += 1
                if maximum is not None and n_output >= maximum:
                    return

    def pull_statuses(
        self,
        username: str | None = None,
        replies: bool = False,
        verbose: bool = False,
        created_after: datetime | None = None,
        since_id: str | int | None = None,
        pinned: bool = False,
        *,
        user_id: str | None = None,
    ) -> Iterator[dict]:
        """Pull the given user's statuses.

        Pass either `username` or `user_id`. Supplying `user_id` directly skips
        an extra `lookup` call, which matters when `lookup` is not available
        (e.g. in public mode, if Truth Social gates that endpoint).

        Params:
            created_after : timezone aware datetime object
            since_id : number or string

        Yields posts in reverse chronological order.
        """
        self.__check_login()
        if user_id is None:
            if username is None:
                raise ValueError("pull_statuses requires either `username` or `user_id`.")
            user = self.lookup(username)
            if user is None:
                return
            user_id = user["id"]

        params: dict = {}
        page_counter = 0
        keep_going = True
        while keep_going:
            try:
                url = f"/v1/accounts/{user_id}/statuses"
                if pinned:
                    url += "?pinned=true&with_muted=true"
                elif not replies:
                    url += "?exclude_replies=true"
                if verbose:
                    logger.debug("--------------------------")
                    logger.debug(f"{url} {params}")
                result = self._get(url, params=params)
                page_counter += 1
            except json.JSONDecodeError as e:
                logger.error(f"Unable to pull user #{user_id}'s statuses': {e}")
                break
            except CFBlockException:
                raise
            except Exception as e:
                logger.error(f"Misc. error while pulling statuses for {user_id}: {e}")
                break

            if result is None:
                break
            if isinstance(result, dict) and "error" in result:
                logger.error(
                    f"API returned an error while pulling user #{user_id}'s statuses: {result}"
                )
                break
            if not isinstance(result, list):
                logger.error(f"Result is not a list (it's a {type(result)}): {result}")
                break
            if len(result) == 0:
                break

            posts: list[dict] = sorted(
                cast(list[dict], result), key=lambda k: k["id"], reverse=True
            )  # reverse chronological order (recent first, older last)
            params["max_id"] = posts[-1][
                "id"
            ]  # when pulling the next page, get posts before this (the oldest)

            if verbose:
                logger.debug(f"PAGE: {page_counter}")

            if pinned:  # assume single page
                keep_going = False

            for post in posts:
                post["_pulled"] = datetime.now().isoformat()

                # only keep posts created after the specified date
                # exclude posts created before the specified date
                # since the page is listed in reverse chronology, we don't need any remaining posts on this page either
                post_at = date_parse.parse(post["created_at"]).replace(tzinfo=UTC)
                if (created_after and post_at <= created_after) or (
                    since_id and int(post["id"]) <= int(since_id)
                ):
                    keep_going = False  # stop the loop, request no more pages
                    break  # do not yeild this post or remaining (older) posts on this page

                if verbose:
                    logger.debug(f"{post['id']} {post['created_at']}")

                yield post

    def get_auth_id(self, username: str, password: str) -> str:
        """Logs in to Truth account and returns the session token"""
        url = BASE_URL + "/oauth/v2/token"
        try:
            payload = {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "grant_type": "password",
                "username": username,
                "password": password,
                "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
                "scope": "read",
            }

            sess_req = requests.request(
                "POST",
                url,
                json=payload,
                proxies=proxies,
                impersonate=IMPERSONATE_TARGET,
                headers={
                    "User-Agent": USER_AGENT,
                },
            )

            # Check for 403 errors and identify the specific type
            if sess_req.status_code == 403:
                response_text = sess_req.text.lower()

                # Check for geographic restriction
                if "unavailable in your area" in response_text:
                    logger.error("Geographic restriction detected")
                    raise GeoblockException("Truth Social is unavailable in your area.")

                # Check for Cloudflare block
                if "you have been blocked" in response_text:
                    logger.error("Cloudflare block detected")
                    raise CFBlockException("Request blocked by Cloudflare.")

                # Generic 403 error
                logger.error(f"403 Forbidden: {response_text[:200]}")
                raise LoginErrorException(
                    f"Authentication forbidden (403). Response: {response_text[:200]}"
                )

            sess_req.raise_for_status()
        except requests.RequestsError as e:
            logger.error(f"Failed login request: {e!s}")
            raise LoginErrorException("Cannot authenticate to .") from e

        if not sess_req.json()["access_token"]:
            raise ValueError("Invalid truthsocial.com credentials provided!")

        return sess_req.json()["access_token"]
