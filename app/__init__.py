from flask import Flask
from flasgger import Swagger
from flask_jwt_extended import JWTManager
from app.sample.view import app_sample
from app.auth.view import app_auth
from app.host.view import app_host
from app.admin.view import app_admin
from app.user.view import app_user
from app.log.view import app_log
from src import FLASK_JSON_PATH
import json

app = Flask(__name__)
template = {
    "swagger": "2.0",
    # "openapi": "3.0.0",
    "info": {
        "title": "ContainerTool API",
        "description": "主機與容器管理 API",
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
    "operationId": "getmyData",
    "securityDefinitions": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "JWT token，格式: Bearer <token>"
        }
    }
}

swagger = Swagger(app, template=template)
jwt = JWTManager(app)


@app.route("/")
def status():
    return 'ok'


def create_app(confgi_object=None):
    app.register_blueprint(blueprint=app_sample, url_prefix='/sample')
    app.register_blueprint(blueprint=app_auth, url_prefix='/auth')
    app.register_blueprint(blueprint=app_host, url_prefix='/host')
    app.register_blueprint(blueprint=app_admin, url_prefix='/admin')
    app.register_blueprint(blueprint=app_user, url_prefix='/user')
    app.register_blueprint(blueprint=app_log, url_prefix='/log')
    if confgi_object:
        app.config.from_object(confgi_object)
    return app
