import re


def is_valid_domain(domain):
    """判斷是否 域名 格式

    Args:
        domain (_type_): _description_

    Returns:
        _type_: _description_
    """
    domain_pattern = r'^([a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
    match_result = re.match(domain_pattern, domain)
    return bool(match_result)
