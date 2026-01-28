from typing import Dict, List

# Valid role names for DM permissions
ALL_ROLES = ["owner", "admin", "mentor", "student", "parent", "faculty"]


def get_default_permission_matrix() -> Dict[str, List[str]]:
    """
    Default DM permission matrix.

    Semantics:
    - Owners/admins: Full access to everyone.
    - Mentors: Can see/DM other mentors, their students, and parents by default.
      (Owners/admins are always added automatically in filtering logic.)
    - Students: Can see/DM mentors.
    - Parents: Can see/DM mentors, faculty, and students.
    - Faculty: Can see/DM mentors and students.
    """
    return {
        "owner": ALL_ROLES,
        "admin": ALL_ROLES,
        # Mentors can see/DM other mentors, students, and parents.
        # Owners/admins are always allowed in get_allowed_target_roles.
        "mentor": ["mentor", "student", "parent", "faculty"],
        "student": ["mentor"],
        "parent": ["mentor", "faculty", "student"],
        "faculty": ["mentor", "student"],
    }
