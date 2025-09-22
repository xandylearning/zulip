# Guest Role Removal - Changes Documentation

## Overview

This document details the changes made to remove the guest role functionality from the Zulip system and replace it with the new custom role system (Faculty, Student, Parent, Mentor).

## Files Modified

### 1. `corporate/views/portico.py`

**Location**: `/Users/straxs/Work/zulip/corporate/views/portico.py`

**Changes Made**:

#### Line 113: Role Check Update
```python
# BEFORE:
if request.user.is_guest:
    return TemplateResponse(request, "404.html", status=404)

# AFTER:
if request.user.role in [UserProfile.ROLE_STUDENT, UserProfile.ROLE_PARENT]:
    return TemplateResponse(request, "404.html", status=404)
```

**Impact**: 
- **Function**: `plans_view()` - Controls access to billing/plans page
- **Change**: Replaced `is_guest` property check with role-based check
- **Logic**: Students and Parents (limited access users) are now blocked from accessing billing pages
- **Reasoning**: Limited access users shouldn't have billing permissions

---

### 2. `corporate/views/upgrade.py`

**Location**: `/Users/straxs/Work/zulip/corporate/views/upgrade.py`

**Changes Made**:

#### Line 193: Role Check Update
```python
# BEFORE:
if not settings.BILLING_ENABLED or user.is_guest:
    return render(request, "404.html", status=404)

# AFTER:
if not settings.BILLING_ENABLED or user.role in [UserProfile.ROLE_STUDENT, UserProfile.ROLE_PARENT]:
    return render(request, "404.html", status=404)
```

**Impact**:
- **Function**: `upgrade_page()` - Controls access to upgrade/billing page
- **Change**: Replaced `is_guest` property check with role-based check
- **Logic**: Students and Parents are blocked from accessing upgrade functionality
- **Reasoning**: Limited access users shouldn't be able to upgrade billing plans

---

## Role System Context

### Old System (Removed)
- **Guest Role**: `UserProfile.ROLE_GUEST` (value: 600)
- **Property**: `user.is_guest` - Boolean property indicating guest status
- **Permissions**: Limited access to channels, no billing access

### New System (Current)
- **Student Role**: `UserProfile.ROLE_STUDENT` (value: 500)
- **Parent Role**: `UserProfile.ROLE_PARENT` (value: 550)
- **Faculty Role**: `UserProfile.ROLE_FACULTY` (value: 400)
- **Mentor Role**: `UserProfile.ROLE_MENTOR` (value: 300)

### Limited Access Users
The new system considers **Students** and **Parents** as "limited access users" who:
- Have restricted permissions
- Cannot access billing/upgrade functionality
- Cannot manage organization settings
- Have limited communication capabilities

## Business Logic Impact

### Billing Access Control
Both changes implement the same business rule:
- **Limited access users** (Students/Parents) cannot access billing functionality
- This prevents unauthorized billing changes
- Maintains security for educational institutions

### Permission Hierarchy
```
Realm Owner (100) > Realm Admin (200) > Faculty (400) > Mentor (300) > Parent (550) > Student (500)
```

**Billing Access**: Only users with roles 100-400 can access billing
**Limited Access**: Users with roles 500+ have restricted permissions

## Related Changes

These changes are part of a larger refactoring that also updated:

1. **Analytics Views**: `analytics/views/stats.py` - Stats page access control
2. **Frontend Templates**: Multiple `.hbs` files - UI permission checks
3. **TypeScript Types**: `web/src/state_data.ts` - Frontend type definitions
4. **User Models**: `zerver/models/users.py` - Added `user_is_limited_access` property
5. **Event System**: `zerver/lib/events.py` - User data serialization
6. **API Responses**: `zerver/lib/users.py` - API user data formatting

## Testing Considerations

### What to Test
1. **Student users** cannot access `/plans/` page
2. **Parent users** cannot access `/plans/` page  
3. **Student users** cannot access upgrade functionality
4. **Parent users** cannot access upgrade functionality
5. **Faculty/Mentor users** can still access billing features
6. **Admin users** retain full access

### Test Cases
```python
# Test that limited access users get 404
def test_student_cannot_access_plans():
    student = create_user_with_role(UserProfile.ROLE_STUDENT)
    response = client.get('/plans/', user=student)
    assert response.status_code == 404

def test_parent_cannot_access_upgrade():
    parent = create_user_with_role(UserProfile.ROLE_PARENT)
    response = client.get('/upgrade/', user=parent)
    assert response.status_code == 404
```

## Migration Notes

### Database Impact
- No database schema changes required
- Existing guest users should be migrated to appropriate new roles
- Role values are already defined in the system

### Backward Compatibility
- Old `is_guest` property references will cause runtime errors
- All references must be updated to use role-based checks
- Frontend code updated to use `is_limited_access` property

## Security Implications

### Access Control
- **Improved**: More granular role-based permissions
- **Maintained**: Billing access restrictions for limited users
- **Enhanced**: Clear separation between educational roles

### Data Protection
- Students/Parents cannot accidentally modify billing settings
- Prevents unauthorized subscription changes
- Maintains institutional control over billing

## Future Considerations

### Potential Enhancements
1. **Role-specific billing**: Different billing rules per role
2. **Parent billing access**: Allow parents to view (but not modify) billing
3. **Student payment**: Allow students to make limited payments
4. **Audit logging**: Track role-based access attempts

### Configuration Options
Consider adding settings for:
- `ALLOW_STUDENT_BILLING_ACCESS`
- `ALLOW_PARENT_BILLING_ACCESS`
- `CUSTOM_ROLE_BILLING_PERMISSIONS`

---

## Summary

These changes successfully remove the deprecated guest role system and replace it with a more flexible, educational-focused role system. The billing access controls ensure that only appropriate users can modify subscription and billing settings, maintaining security while providing the flexibility needed for educational institutions.

**Files Changed**: 2
**Lines Modified**: 2
**Business Logic**: Maintained (limited access users blocked from billing)
**Security**: Enhanced (role-based access control)
