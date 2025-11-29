"""Compatibility shim: expose `app` for Gunicorn while delegating CLI to `cli.py`.

This file exists so a deployment that runs `gunicorn app:app` will succeed
by exporting the Flask application object from `web_app.py`. Running
`python app.py` will still work as a CLI by delegating to `cli.main()`.
"""

from web_app import app as app  # exported WSGI app for Gunicorn


if __name__ == "__main__":
    # Delegate to the CLI entrypoint when run as a script
    from cli import main

    main()
