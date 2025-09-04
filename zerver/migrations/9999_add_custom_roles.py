# Generated manually to add custom roles

from django.db import migrations, models
import django.db.models.deletion


def create_custom_role_groups(apps, schema_editor):
    """Create system groups for the new custom roles."""
    UserGroup = apps.get_model("zerver", "UserGroup")
    NamedUserGroup = apps.get_model("zerver", "NamedUserGroup")
    Realm = apps.get_model("zerver", "Realm")
    
    # Create system groups for each realm
    for realm in Realm.objects.all():
        try:
            # Get existing system groups for this realm
            administrators_group = NamedUserGroup.objects.get(realm=realm, name="role:administrators")
            nobody_group = NamedUserGroup.objects.get(realm=realm, name="role:nobody")
            everyone_group = NamedUserGroup.objects.get(realm=realm, name="role:everyone")
            
            # Faculty group
            faculty_group = NamedUserGroup.objects.create(
                realm=realm,
                name="role:faculty",
                description="Faculty members of this organization",
                is_system_group=True,
                can_add_members_group=administrators_group,
                can_join_group=nobody_group,
                can_leave_group=nobody_group,
                can_manage_group=administrators_group,
                can_mention_group=everyone_group,
                can_remove_members_group=administrators_group,
            )
            
            # Students group
            students_group = NamedUserGroup.objects.create(
                realm=realm,
                name="role:students",
                description="Students of this organization",
                is_system_group=True,
                can_add_members_group=administrators_group,
                can_join_group=nobody_group,
                can_leave_group=nobody_group,
                can_manage_group=administrators_group,
                can_mention_group=everyone_group,
                can_remove_members_group=administrators_group,
            )
            
            # Parents group
            parents_group = NamedUserGroup.objects.create(
                realm=realm,
                name="role:parents",
                description="Parents of this organization",
                is_system_group=True,
                can_add_members_group=administrators_group,
                can_join_group=nobody_group,
                can_leave_group=nobody_group,
                can_manage_group=administrators_group,
                can_mention_group=everyone_group,
                can_remove_members_group=administrators_group,
            )
            
            # Mentors group
            mentors_group = NamedUserGroup.objects.create(
                realm=realm,
                name="role:mentors",
                description="Mentors of this organization",
                is_system_group=True,
                can_add_members_group=administrators_group,
                can_join_group=nobody_group,
                can_leave_group=nobody_group,
                can_manage_group=administrators_group,
                can_mention_group=everyone_group,
                can_remove_members_group=administrators_group,
            )
        except Exception as e:
            print(f"Error creating groups for realm {realm.id}: {e}")


def reverse_custom_role_groups(apps, schema_editor):
    """Remove the custom role groups."""
    NamedUserGroup = apps.get_model("zerver", "NamedUserGroup")
    
    # Remove the custom role groups
    NamedUserGroup.objects.filter(
        name__in=["role:faculty", "role:students", "role:parents", "role:mentors"]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('zerver', '0751_externalauthid_zerver_user_externalauth_uniq'),
    ]

    operations = [
        migrations.RunPython(
            create_custom_role_groups,
            reverse_custom_role_groups,
            elidable=False,
        ),
    ]
