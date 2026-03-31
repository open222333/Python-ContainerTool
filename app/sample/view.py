from flask import Blueprint, jsonify
from flasgger import swag_from
from src.sample import is_valid_domain
import os

app_sample = Blueprint(
    name='sample',
    import_name=__name__
)


@app_sample.route('/check/<domain>', methods=['GET'])
@swag_from(os.path.join('doc', 'sample.yaml'))
def check(domain):
    try:
        result = is_valid_domain(domain)
        if result:
            return jsonify({
                "success": True,
                "result": f'{domain} 符合域名格式'
            }), 200
        else:
            return jsonify({
                "success": True,
                "result": f'{domain} 不符合域名格式'
            }), 200
    except Exception as err:
        return jsonify({
            "success": False,
            "result": f'發生錯誤 {err}'
        }), 500
