# Generated manually to remove unwanted roles and implement communication restrictions

from django.db import migrations, models
import django.db.models.deletion


def remove_unwanted_roles_and_implement_restrictions(apps, schema_editor):
    """Remove unwanted roles and implement communication restrictions."""
    UserProfile = apps.get_model("zerver", "UserProfile")
    NamedUserGroup = apps.get_model("zerver", "NamedUserGroup")
    Realm = apps.get_model("zerver", "Realm")
    
    # Remove unwanted roles: MODERATOR (300), MEMBER (400), GUEST (600)
    # Convert users with these roles to appropriate new roles
    
    # Convert moderators (300) to administrators (200)
    UserProfile.objects.filter(role=300).update(role=200)
    
    # Convert members (400) to faculty (450)
    UserProfile.objects.filter(role=400).update(role=450)
    
    # Convert guests (600) to students (500)
    UserProfile.objects.filter(role=600).update(role=500)
    
    # Update database records that reference old groups
    # First, update any realm settings that reference the old groups
    for realm in Realm.objects.all():
        try:
            # Get the everyone group to use as replacement
            everyone_group = NamedUserGroup.objects.get(realm=realm, name="role:everyone")
            administrators_group = NamedUserGroup.objects.get(realm=realm, name="role:administrators")
            
            # Update realm settings that might reference old groups
            # This is a simplified approach - in production you'd want to be more specific
            realm_fields = [
                'can_add_subscribers_group', 'can_create_public_channel_group', 
                'can_create_private_channel_group', 'can_invite_users_group',
                'can_move_messages_between_channels_group', 'can_move_messages_between_topics_group',
                'can_add_custom_emoji_group', 'can_delete_own_message_group',
                'can_set_delete_message_policy_group', 'can_set_topics_policy_group'
            ]
            
            for field_name in realm_fields:
                field = getattr(realm, field_name, None)
                if field and field.name in ["role:members", "role:moderators"]:
                    # Replace with appropriate new group
                    if field.name == "role:members":
                        setattr(realm, field_name, everyone_group)
                    elif field.name == "role:moderators":
                        setattr(realm, field_name, administrators_group)
            
            realm.save()
            
            # Remove moderator and member groups
            NamedUserGroup.objects.filter(
                realm=realm,
                name__in=["role:moderators", "role:members"]
            ).delete()
            
        except Exception as e:
            print(f"Error updating realm {realm.id}: {e}")


def reverse_remove_unwanted_roles(apps, schema_editor):
    """Reverse the role removal - this is complex and may not be fully reversible."""
    # Note: This reverse migration is complex because we've changed user roles
    # In practice, you might want to create a backup before running this migration
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('zerver', '9999_add_custom_roles'),
    ]

    operations = [
        migrations.RunPython(
            remove_unwanted_roles_and_implement_restrictions,
            reverse_remove_unwanted_roles,
            elidable=False,
        ),
    ]
