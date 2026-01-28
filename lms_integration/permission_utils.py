from typing import Dict, List

# Valid role names for DM permissions
ALL_ROLES = ["owner", "admin", "mentor", "student", "parent", "faculty"]

def get_default_permission_matrix() -> Dict[str, List[str]]:
    return {
        "owner": ALL_ROLES,
        "admin": ALL_ROLES,
        "mentor": ALL_ROLES,
        "student": ["mentor"],
        "parent": ["mentor", "faculty", "student"],
        "faculty": ["mentor", "student"],
    }
