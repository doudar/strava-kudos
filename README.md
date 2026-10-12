# Strava Kudos Giver 👍👍👍

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/) ![Github Actions](https://github.com/isaac-chung/strava-kudos/actions/workflows/give_kudos.yml/badge.svg)

A Python tool to automatically give [Strava](https://www.strava.com) Kudos to recent activities on your feed. There are a few repos that uses JavaScript like [strava-kudos-lambda](https://github.com/mjad-org/strava-kudos-lambda) and [strava-kudos](https://github.com/rnvo/strava-kudos). 

The repo is set up so that the script runs on a set schedule via Github Actions. Github suggests in their [docs](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#schedule) to not run cron jobs at the start of every hour to avoid delays so minute30 was chosen here. Feel free to change it to whenever you want. There is also a `max_run_duration` parameter which is 9 minutes by default so that we don't exceed the [monthly Github Action free tier minutes](https://docs.github.com/en/billing/managing-billing-for-github-actions/about-billing-for-github-actions#included-storage-and-minutes) when the action is triggered a few times a day.

## 🏃 Usage
1. Fork the repo
2. Setup the environment variables in secrets
3. Give kudos automatically!

Alternatively, use Docker as described below, or install the local dependencies and run the script manually with
```
python3 give_kudos.py
```

## 🛠️Setup

### Playwright
[Playwright](https://github.com/microsoft/playwright-python) is used with Firefox. GitHub Actions and the Dockerfile use `mcr.microsoft.com/playwright/python:v1.63.0-noble`, which includes the browsers and their system dependencies. The Python Playwright package is installed from `requirements.txt`; no browser download is needed during an Actions job or when building the application image.

Keep the Playwright version in `requirements.txt`, `Dockerfile`, and `.github/workflows/give_kudos.yml` identical. The installed Python package must match the browsers supplied by the image. See the [Playwright Docker documentation](https://playwright.dev/python/docs/docker).

To run outside Docker, use Python 3.10 or newer and install the dependencies first:

```sh
python -m pip install -r requirements.txt
python -m playwright install --with-deps firefox
```

### Docker

With Docker running in Linux container mode, build the application image from the repository root:

```sh
docker build -t strava-kudos .
```

Create a local `.env` file containing your Strava credentials:

```dotenv
STRAVA_EMAIL=YOUR_EMAIL
STRAVA_PASSWORD=YOUR_PASSWORD
```

The `.env` file is ignored by Git and excluded from the Docker build context. Pass it at runtime:

```sh
docker run --rm --init --env-file .env strava-kudos
```

Each container run gives kudos once and exits. To run repeatedly outside GitHub Actions, schedule this command with your host's scheduler.

To check the bundled Firefox browser without signing into Strava or giving kudos:

```sh
docker run --rm --init --network none strava-kudos python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); b = p.firefox.launch(); page = b.new_page(); page.set_content('<title>Smoke test</title>'); assert page.title() == 'Smoke test'; b.close(); p.stop(); print('Firefox smoke test passed')"
```

### Environment Variables

Set the environment variables for your email and password as follows:
```
export STRAVA_EMAIL=YOUR_EMAIL
export STRAVA_PASSWORD=YOUR_PASSWORD
```

### Github Actions
To add secrets for GH actions, navigate to Settings -> Security -> Secrets and Variables -> Actions. Enter your email and password within `Repository Secrets`.

The scheduled and manually dispatched jobs run inside the Playwright Python container. Python, Firefox, and browser system libraries come from the image; the job only installs the Python dependencies before running `give_kudos.py`. You can start a manual run from Actions -> Give Strava Kudos -> Run workflow.

## 🔬Testing
The original script was manually tested with Python 3.9.10 on Ubuntu 20.04.6. The current container uses Python 3.12 on Ubuntu 24.04 and Playwright 1.63.0. Use the Docker smoke-test command above to verify Firefox launches before running against your Strava account.

## Contributions
Let me know if you wish to add anything or if there are any issues!

[![ForTheBadge built-with-love](http://ForTheBadge.com/images/badges/built-with-love.svg)](https://GitHub.com/Naereen/)
