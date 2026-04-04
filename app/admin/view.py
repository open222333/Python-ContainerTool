from flask import Blueprint, render_template

app_admin = Blueprint('app_admin', __name__)


@app_admin.route('/')
def index():
    return render_template('admin/index.html')
