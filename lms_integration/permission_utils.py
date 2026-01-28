from typing import Dict, List

def get_default_permission_matrix() -> Dict[str, List[str]]:
    return {
        "owner": ["owner", "admin", "mentor", "student"],
        "admin": ["owner", "admin", "mentor", "student"],
        "mentor": ["owner", "admin", "mentor", "student"],
        "student": ["mentor"],
    }
