import os
from flask import Blueprint, render_template, render_template_string, abort
from src import APP_TITLE

app_admin = Blueprint('app_admin', __name__)

_DOCS_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{ title }}</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body { background: #f5f6fa; }
    .doc-body { max-width: 860px; margin: 2rem auto; padding: 2rem; background: #fff; border-radius: 10px; box-shadow: 0 2px 12px rgba(0,0,0,.08); }
    pre { background: #1e2130; color: #c9d1d9; border-radius: 6px; padding: 1rem; overflow-x: auto; }
    code { font-size: .875em; }
    pre code { color: inherit; background: none; }
    table { width: 100%; border-collapse: collapse; margin: 1rem 0; }
    th, td { border: 1px solid #dee2e6; padding: .5rem .75rem; }
    th { background: #f1f3f5; }
    blockquote { border-left: 4px solid #6384ff; padding: .5rem 1rem; background: #f0f4ff; border-radius: 0 6px 6px 0; color: #444; }
  </style>
</head>
<body>
  <div class="doc-body">
    <a href="javascript:history.back()" class="btn btn-sm btn-outline-secondary mb-3">&larr; 返回</a>
    <div id="content"></div>
  </div>
  <script src="https://cdn.jsdelivr.net/npm/marked@9/marked.min.js"></script>
  <script>
    document.getElementById('content').innerHTML = marked.parse({{ raw|tojson }});
  </script>
</body>
</html>"""

_DOCS_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'docs')


@app_admin.route('/')
def index():
    return render_template('admin/index.html', app_title=APP_TITLE)


@app_admin.route('/docs/<path:filename>')
def docs(filename):
    filepath = os.path.join(_DOCS_ROOT, filename + '.md')
    if not os.path.isfile(filepath):
        abort(404)
    with open(filepath, encoding='utf-8') as f:
        content = f.read()
    title = content.splitlines()[0].lstrip('# ').strip() if content else filename
    return render_template_string(_DOCS_TEMPLATE, title=title, raw=content)
