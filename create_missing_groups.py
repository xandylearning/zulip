#!/usr/bin/env python3
"""
Script to create missing system groups for custom roles.
This script should be run after the migration to ensure all realms have the required system groups.
"""

import os
import sys
import django

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'zproject.settings')
django.setup()

from zerver.models import Realm, NamedUserGroup, UserGroup


def create_missing_system_groups():
    """Create missing system groups for all realms."""
    from zerver.models.groups import SystemGroups
    
    realms = Realm.objects.all()
    
    for realm in realms:
        print(f"Processing realm: {realm.name} (ID: {realm.id})")
        
        # Get existing system groups
        existing_groups = NamedUserGroup.objects.filter(
            realm=realm, 
            is_system_group=True
        ).values_list('name', flat=True)
        
        # Get required system groups
        required_groups = [
            SystemGroups.OWNERS,
            SystemGroups.ADMINISTRATORS,
            SystemGroups.FACULTY,
            SystemGroups.STUDENTS,
            SystemGroups.PARENTS,
            SystemGroups.MENTORS,
            SystemGroups.EVERYONE,
            SystemGroups.NOBODY,
        ]
        
        # Find missing groups
        missing_groups = [group for group in required_groups if group not in existing_groups]
        
        if missing_groups:
            print(f"  Missing groups: {missing_groups}")
            
            # Get reference groups
            try:
                administrators_group = NamedUserGroup.objects.get(realm=realm, name=SystemGroups.ADMINISTRATORS)
                nobody_group = NamedUserGroup.objects.get(realm=realm, name=SystemGroups.NOBODY)
                everyone_group = NamedUserGroup.objects.get(realm=realm, name=SystemGroups.EVERYONE)
            except NamedUserGroup.DoesNotExist as e:
                print(f"  Error: Required reference group not found: {e}")
                continue
            
            # Create missing groups
            for group_name in missing_groups:
                try:
                    if group_name == SystemGroups.FACULTY:
                        group = NamedUserGroup.objects.create(
                            realm=realm,
                            name=group_name,
                            description="Faculty members of this organization",
                            is_system_group=True,
                            can_add_members_group=administrators_group,
                            can_join_group=nobody_group,
                            can_leave_group=nobody_group,
                            can_manage_group=administrators_group,
                            can_mention_group=everyone_group,
                            can_remove_members_group=administrators_group,
                        )
                    elif group_name == SystemGroups.STUDENTS:
                        group = NamedUserGroup.objects.create(
                            realm=realm,
                            name=group_name,
                            description="Students of this organization",
                            is_system_group=True,
                            can_add_members_group=administrators_group,
                            can_join_group=nobody_group,
                            can_leave_group=nobody_group,
                            can_manage_group=administrators_group,
                            can_mention_group=everyone_group,
                            can_remove_members_group=administrators_group,
                        )
                    elif group_name == SystemGroups.PARENTS:
                        group = NamedUserGroup.objects.create(
                            realm=realm,
                            name=group_name,
                            description="Parents of this organization",
                            is_system_group=True,
                            can_add_members_group=administrators_group,
                            can_join_group=nobody_group,
                            can_leave_group=nobody_group,
                            can_manage_group=administrators_group,
                            can_mention_group=everyone_group,
                            can_remove_members_group=administrators_group,
                        )
                    elif group_name == SystemGroups.MENTORS:
                        group = NamedUserGroup.objects.create(
                            realm=realm,
                            name=group_name,
                            description="Mentors of this organization",
                            is_system_group=True,
                            can_add_members_group=administrators_group,
                            can_join_group=nobody_group,
                            can_leave_group=nobody_group,
                            can_manage_group=administrators_group,
                            can_mention_group=everyone_group,
                            can_remove_members_group=administrators_group,
                        )
                    
                    print(f"  Created group: {group_name}")
                    
                except Exception as e:
                    print(f"  Error creating group {group_name}: {e}")
        else:
            print("  All required groups exist")


if __name__ == "__main__":
    print("Creating missing system groups for custom roles...")
    create_missing_system_groups()
    print("Done!")