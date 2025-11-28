"""WSGI entry point for production cloud servers (Heroku, Render, Railway, etc.)"""
from web_app import app

if __name__ == "__main__":
    app.run()
