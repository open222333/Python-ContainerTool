from flask import Flask
from flasgger import Swagger
from app.sample.view import app_sample
from src import FLASK_JSON_PATH
import json

app = Flask(__name__)
template = {
    "swagger": "2.0",
    # "openapi": "3.0.0",
    "info": {
        "title": "My API",
        "description": "練習用 API文檔",
        "contact": {
            "responsibleOrganization": "ME",
            "responsibleDeveloper": "Me",
            "email": "open222333@gmail.com",
            "url": "www.test.com",
        },
        "termsOfService": "http://test.com/terms",
        "version": "0.0.1"
    },
    "host": "127.0.0.1",  # overrides localhost:500
    "basePath": "/",  # base bash for blueprint registration
    "schemes": [
        "http",
        # "https"
    ],
    "operationId": "getmyData"
}

swagger = Swagger(app, template=template)


@app.route("/")
def status():
    return 'ok'


def create_app(confgi_object=None):
    app.register_blueprint(blueprint=app_sample, url_prefix='/sample')
    if confgi_object:
        app.config.from_object(confgi_object)
    return app
