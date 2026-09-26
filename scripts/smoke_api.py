"""Validate the live HTTP contract, not Flask's in-process test client."""
import argparse
import json
import time
from urllib.error import URLError
from urllib.request import urlopen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('url')
    parser.add_argument('--attempts', type=int, default=5)
    args = parser.parse_args()
    for attempt in range(args.attempts):
        try:
            with urlopen(args.url, timeout=5) as response:
                assert response.status == 200, 'Expected HTTP 200'
                assert response.headers.get_content_type() == 'application/json'
                assert json.load(response) == {'status': 'ok', 'service': 'us-accidents-api'}
            print('PASS: live API HTTP health contract')
            return
        except (URLError, AssertionError, ValueError):
            if attempt == args.attempts - 1:
                raise
            time.sleep(1)


if __name__ == '__main__':
    main()
