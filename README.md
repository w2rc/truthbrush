# truthbrush
Truthbrush is an API client for Truth Social.

Currently, this tool can:

* Search for users, statuses, groups, or hashtags
* Pull a user's statuses
* Pull the list of "People to Follow" or suggested users
* Pull "trending" hashtags
* Pull "trending" Truth posts
* Pull ads
* Pull a user's metadata
* Pull the list of users who liked a post
* Pull the list of comments on a post
* Pull "trending" groups
* Pull list of suggested groups
* Pull "trending" group hashtags
* Pull posts from group timeline

Truthbrush is designed for academic research, open source intelligence gathering, and data archival. It pulls all data from the publicly accessible API.

## Installation

From PyPi:

```sh
pip install truthbrush
```

From git:

* To install it, run `pip install git+https://github.com/stanfordio/truthbrush.git`

From source:

* Clone the repository and run `pip3 install .`. Provided your `pip` is setup correctly, this will make `truthbrush` available both as a command and as a Python package.

After installation, you will need to set your Truth Social username and password as environmental variables.

`export TRUTHSOCIAL_USERNAME=foo`

`export TRUTHSOCIAL_PASSWORD=bar`

If you encounter login issues, you can instead extract your login token from the truth:auth Local Storage store and export it in `TRUTHSOCIAL_TOKEN`.

You may also set these variables in a `.env` file in the directory from which you are running Truthbrush.

### Public mode (no credentials)

Some Truth Social endpoints are readable without authentication. To run Truthbrush against only those endpoints, pass `--no-auth` on the CLI or construct the client with `require_auth=False`:

```sh
truthbrush --no-auth trends
truthbrush --no-auth user realDonaldTrump
```

```py
from truthbrush import Api

api = Api(require_auth=False)
print(api.trending())
```

Endpoints that require authentication will return an API error (typically HTTP 401) when called in public mode. Which endpoints are publicly accessible is determined by Truth Social and may change without notice.

## CLI Usage

```text
Usage: truthbrush [OPTIONS] COMMAND [ARGS]...

Options:
  --no-auth  Run without authentication. Only public endpoints will succeed.
  --help     Show this message and exit.


Commands:
  search            Search for users, statuses or hashtags.
  statuses          Pull a user's statuses.
  suggestions       Pull the list of suggested users.
  tags              Pull trendy tags.
  trends            Pull trendy Truths.
  ads               Pull ads.
  user              Pull a user's metadata.
  likes             Pull the list of users who liked a post
  comments          Pull the list of oldest comments on a post
  groupposts        Pull posts from a groups's timeline
  grouptags         Pull trending group tags.
  grouptrends       Pull trending groups.
  groupsuggestions  Pull list of suggested groups.

```

**Search for users, statuses, groups, or hashtags**

```bash
truthbrush search --searchtype [accounts|statuses|hashtags|groups] QUERY
```

Restrict status results to a date window:

```bash
truthbrush search --searchtype statuses --start-date 2024-11-01 --end-date 2024-11-07 QUERY
```

**Pull all statuses (posts) from a user**

```bash
truthbrush statuses HANDLE
```

Restrict to a date window (UTC assumed when no timezone is given):

```bash
truthbrush statuses --created-after 2024-11-01 --created-before 2024-11-07 HANDLE
```

**Pull "People to Follow" (suggested) users**

```bash
truthbrush suggestions
```

**Pull trendy tags**

```bash
truthbrush tags
```

**Pull ads**

```bash
truthbrush ads
```

**Pull all of a user's metadata**

```bash
truthbrush user HANDLE
```

**Pull the list of users who liked a post**

```bash
truthbrush likes POST --includeall TOP_NUM
```

**Pull the list of oldest comments on a post**

```bash
truthbrush comments POST --includeall --onlyfirst TOP_NUM
```

**Pull trending group tags**

```bash
truthbrush grouptags
```

**Pull trending groups**

```bash
truthbrush grouptrends
```

**Pull list of suggested groups**

```bash
truthbrush groupsuggestions
```

**Pull posts from a group's timeline**

```bash
truthbrush groupposts GROUP_ID
```

## Contributing

Contributions are encouraged! For small bug fixes and minor improvements, feel free to just open a PR. For larger changes, please open an issue first so that other contributors can discuss your plan, avoid duplicated work, and ensure it aligns with the goals of the project. Be sure to also follow the [code of conduct](CODE_OF_CONDUCT.md). Thanks!

Development setup (ensure you have [Poetry](https://python-poetry.org/) installed):

```sh
poetry install
poetry shell
truthbrush --help # will use your local copy of truthbrush
```

To run the tests:

```sh
pytest

# optionally run tests with verbose logging outputs:
pytest --log-cli-level=DEBUG -s
```

Please format and lint your code with `ruff`, and run `ty` to check types:

```sh
ruff format .
ruff check .
ty check truthbrush/
```
