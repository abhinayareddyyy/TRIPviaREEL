"""TripViaReel - Flask application entry point.

Run:  python -m app.main      (from the project root)
Or:   flask --app app.main:create_app run
"""
from __future__ import annotations

import os
from typing import Optional

from flask import Flask, jsonify, render_template
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

from app.models import db
from app.routes.api import bp as api_bp
from app.services.geocoding import Gazetteer
from app.services.location_extractor import LocationExtractor

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MAX_UPLOAD_MB = 60


def create_app(config: Optional[dict] = None) -> Flask:
    app = Flask(__name__)
    app.config["DATABASE_PATH"] = os.environ.get("DATABASE_PATH", os.path.join(ROOT, "data", "tripviareel.db"))
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
    if config:
        app.config.update(config)

    gz = Gazetteer.load(app.config.get("PLACES_PATH"))
    app.config["GAZETTEER"] = gz
    app.config["EXTRACTOR"] = LocationExtractor(gz)
    db.init_db(app.config["DATABASE_PATH"])

    app.register_blueprint(api_bp)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.errorhandler(RequestEntityTooLarge)
    def too_large(_e):
        return jsonify({"error": f"Upload too large (max {MAX_UPLOAD_MB} MB in total)."}), 413

    @app.errorhandler(HTTPException)
    def http_error(e):
        return jsonify({"error": e.description}), e.code

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=False)
