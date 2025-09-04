# Custom Roles System Implementation

## Overview

This document describes the implementation of a custom role system for Zulip, replacing the default roles (owner, administrator, moderator, member, guest) with a new set of roles designed for educational institutions: **owner**, **administrator**, **faculty**, **student**, **parent**, and **mentor**.

## Role System Design

### New Role Hierarchy

| Role | Code | Description | Permissions |
|------|------|-------------|-------------|
| Owner | 100 | Realm owner | Full administrative access |
| Administrator | 200 | Realm administrator | Administrative access |
| Faculty | 450 | Faculty members | Full member access |
| Student | 500 | Students | Limited access |
| Parent | 550 | Parents | Limited access |
| Mentor | 600 | Mentors | Full member access |

### Communication Restrictions

The system implements specific communication restrictions:

- **Students** cannot communicate with other students
- **Parents** cannot communicate with other parents
- **Parents** can chat only with mentors, faculty, and students
- **Students** can chat only with mentors
- **Mentors** can chat with parents, faculty, and students

## Implementation Details

### 1. Backend Changes

#### UserProfile Model (`zerver/models/users.py`)

**Removed Roles:**
- `ROLE_MODERATOR` (300)
- `ROLE_MEMBER` (400) 
- `ROLE_GUEST` (600)

**Added Roles:**
- `ROLE_FACULTY` (450)
- `ROLE_STUDENT` (500)
- `ROLE_PARENT` (550)
- `ROLE_MENTOR` (600)

**Key Changes:**
- Updated default role from `ROLE_MEMBER` to `ROLE_FACULTY`
- Added new role properties: `is_faculty`, `is_student`, `is_parent`, `is_mentor`
- Implemented `can_communicate_with()` method for communication restrictions
- Updated role type lists, name mappings, and API name mappings

#### System Groups (`zerver/models/groups.py`)

**Removed Groups:**
- `MODERATORS`
- `MEMBERS`
- `GUEST`

**Added Groups:**
- `FACULTY`
- `STUDENTS`
- `PARENTS`
- `MENTORS`

**Updated Mappings:**
- `GROUP_DISPLAY_NAME_MAP`
- `SYSTEM_USER_GROUP_ROLE_MAP`

#### Communication Logic (`zerver/actions/message_send.py`)

- Updated `check_can_send_direct_message()` to use `can_communicate_with()` method
- Modified `limited_access_recipients` filtering logic

### 2. Database Migrations

#### Migration 9999: Add Custom Roles (`zerver/migrations/9999_add_custom_roles.py`)
- Creates new system groups for custom roles
- Sets up proper group relationships and permissions

#### Migration 10000: Remove Unwanted Roles (`zerver/migrations/10000_remove_unwanted_roles.py`)
- Converts existing users to new roles:
  - `MODERATOR` (300) → `ADMINISTRATOR` (200)
  - `MEMBER` (400) → `FACULTY` (450)
  - `GUEST` (600) → `STUDENT` (500)
- Removes old system groups
- Updates realm settings to reference new groups

#### Migration 0001: Update Default Role (`zerver/migrations/0001_squashed_0569.py`)
- Changed default role from `400` (ROLE_MEMBER) to `450` (ROLE_FACULTY)

### 3. Frontend Changes

#### Configuration Files

**`web/src/settings_config.ts`**
- Updated `user_role_values` to include new roles
- Updated `system_user_groups_list` to include new groups

**`web/src/state_data.ts`**
- Added new role properties: `is_faculty`, `is_student`, `is_parent`, `is_mentor`
- Removed old properties: `is_guest`, `is_moderator`

**`web/src/user_events.ts`**
- Updated event handling for new role properties

#### UI Components

**Updated Files:**
- `web/src/people.ts` - User data management
- `web/src/user_card_popover.ts` - User card display
- `web/src/filter.ts` - Message filtering
- `web/src/message_list_view.ts` - Message display
- `web/src/compose_validate.ts` - Message composition validation
- And 20+ other frontend files

**Key Changes:**
- Replaced `guest` terminology with `limited_access`
- Updated role-based UI logic
- Fixed function names and type definitions

### 4. API Changes

#### Backend API (`zerver/lib/users.py`, `zerver/lib/events.py`)

**Updated `APIUserDict` type:**
- Removed: `is_guest`, `is_moderator`
- Added: `is_faculty`, `is_student`, `is_parent`, `is_mentor`

**State Data Updates:**
- Added role properties to frontend state
- Updated user event processing

## Files Modified

### Core Backend Files
- `zerver/models/users.py` - User model and role definitions
- `zerver/models/groups.py` - System groups
- `zerver/actions/message_send.py` - Message sending logic
- `zerver/lib/user_groups.py` - User group utilities
- `zerver/lib/users.py` - User utilities
- `zerver/lib/events.py` - Event processing
- `zerver/actions/users.py` - User actions
- `zerver/actions/user_groups.py` - User group actions
- `zerver/actions/create_user.py` - User creation
- `zerver/lib/bulk_create.py` - Bulk user creation

### Migration Files
- `zerver/migrations/9999_add_custom_roles.py`
- `zerver/migrations/10000_remove_unwanted_roles.py`
- `zerver/migrations/0001_squashed_0569.py`

### Frontend Files (25+ files)
- Configuration: `settings_config.ts`, `state_data.ts`, `user_events.ts`
- Components: `people.ts`, `user_card_popover.ts`, `filter.ts`, etc.
- All files updated to use new role system

### Test Files
- `zerver/tests/test_users.py` - Updated role tests
- Multiple test files updated for new role constants

## Key Issues Resolved

### 1. System Group Creation
- **Issue**: Missing `EVERYONE` group in system groups list
- **Fix**: Added `EVERYONE` group to `system_groups_info_list`

### 2. Database Constraints
- **Issue**: Foreign key constraint violations with `-1` values
- **Fix**: Used valid temporary group IDs instead of `-1`

### 3. NOT NULL Constraints
- **Issue**: NULL values in required group setting fields
- **Fix**: Used first group's ID as temporary value for all settings

### 4. Role References
- **Issue**: Multiple references to removed roles (`ROLE_MEMBER`, `ROLE_MODERATOR`, `ROLE_GUEST`)
- **Fix**: Systematically updated all references to new roles

### 5. System Group References
- **Issue**: References to removed system groups (`MODERATORS`, `MEMBERS`)
- **Fix**: Updated to use new system groups (`ADMINISTRATORS`, `EVERYONE`)

## Testing

### Unit Tests
- Updated `test_users.py` with new role system tests
- Added communication restriction tests
- Updated role assignment tests

### Integration Tests
- Database population tests
- User creation and role assignment tests
- System group creation tests

## Deployment Steps

1. **Run Migrations:**
   ```bash
   python manage.py migrate zerver 9999  # Add custom roles
   python manage.py migrate zerver 10000  # Remove unwanted roles
   ```

2. **Verify System Groups:**
   ```bash
   python manage.py populate_db -n10 --threads=1
   ```

3. **Test Role Functionality:**
   - Create users with different roles
   - Test communication restrictions
   - Verify role-based permissions

## Communication Restriction Logic

The `can_communicate_with()` method in `UserProfile` implements the following logic:

```python
def can_communicate_with(self, other_user):
    # Students can only communicate with mentors
    if self.is_student:
        return other_user.is_mentor
    
    # Parents can communicate with mentors, faculty, and students
    if self.is_parent:
        return other_user.is_mentor or other_user.is_faculty or other_user.is_student
    
    # Mentors can communicate with parents, faculty, and students
    if self.is_mentor:
        return other_user.is_parent or other_user.is_faculty or other_user.is_student
    
    # Faculty and administrators can communicate with everyone
    return True
```

## Future Considerations

1. **Role Permissions**: Consider adding more granular permissions for each role
2. **Group Management**: Implement role-based group management features
3. **Audit Logging**: Add role change audit logging
4. **API Documentation**: Update API documentation for new role system
5. **Migration Tools**: Create tools for migrating existing installations

## Troubleshooting

### Common Issues

1. **Migration Errors**: Ensure all role references are updated before running migrations
2. **Frontend Errors**: Check that all frontend files are updated with new role properties
3. **Database Constraints**: Verify system groups are created properly
4. **Role Assignment**: Ensure users are assigned valid roles

### Debug Commands

```bash
# Check system groups
python manage.py shell -c "from zerver.models.groups import SystemGroups; print(SystemGroups.__dict__)"

# Verify user roles
python manage.py shell -c "from zerver.models.users import UserProfile; print(UserProfile.ROLE_FACULTY)"

# Test communication restrictions
python manage.py shell -c "from zerver.models.users import UserProfile; user = UserProfile.objects.first(); print(user.can_communicate_with(user))"
```

## Conclusion

This implementation successfully replaces Zulip's default role system with a custom educational role system. The new system provides:

- Clear role hierarchy for educational institutions
- Enforced communication restrictions
- Proper system group management
- Comprehensive frontend and backend integration
- Robust migration system for existing installations

The system is now ready for production use in educational environments.