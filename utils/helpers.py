# =========================================================
# 유틸리티 함수
# =========================================================

import json


def safe_json_list(val):
    """
    JSON 문자열을 안전하게 리스트로 변환
    
    Args:
        val: JSON 문자열 또는 리스트
    
    Returns:
        list: 파싱된 리스트
    """
    if isinstance(val, list):
        return val
    if not isinstance(val, str):
        return []
    try:
        return json.loads(val)
    except:
        return []


def nearest_resistance_above(price, levels):
    """
    현재 가격 위의 가장 가까운 저항선 찾기
    
    Args:
        price: 현재 가격
        levels: 저항선 레벨 리스트
    
    Returns:
        float or None: 가장 가까운 저항선 또는 None
    """
    if not levels:
        return None
    candidates = [l for l in levels if l >= price]
    if not candidates:
        return None
    return min(candidates)
