# Send admin notifications

{!admin-only.md!}

Admin notifications allow you to send important announcements and updates to users in your organization. You can send notifications to everyone, specific users, or all subscribers of a channel.

## Send a notification

{start_tabs}

{tab|desktop-web}

1. Click on the **gear** (<i class="fa fa-cog"></i>) icon in the upper right corner.

2. Select **Organization settings**.

3. On the left sidebar, click **Admin Notifications**.

4. Click **Send Notification**.

5. Enter a **Title** for your notification.

6. Write your **Message**. Markdown formatting is supported.

7. Choose who should receive the notification:
   - **All Users**: Send to everyone in the organization
   - **Specific Users**: Select individual recipients
   - **Channel Subscribers**: Send to all subscribers of a channel

8. If sending to specific users or a channel, select the recipients.

9. Click **Send**.

{end_tabs}

## View sent notifications

You can view a history of all notifications sent in your organization:

{start_tabs}

{tab|desktop-web}

1. Click on the **gear** (<i class="fa fa-cog"></i>) icon in the upper right corner.

2. Select **Organization settings**.

3. On the left sidebar, click **Admin Notifications**.

4. The **Sent Notifications** tab shows all notifications with:
   - Title and preview
   - Recipients
   - Sender and timestamp
   - Delivery statistics

5. Click **View Details** on any notification to see:
   - Full message content
   - Detailed delivery statistics
   - Individual recipient status

{end_tabs}

## Use notification templates

Templates allow you to save and reuse common notifications:

### Create a template

{start_tabs}

{tab|desktop-web}

1. Go to **Organization settings** > **Admin Notifications**.

2. Click the **Templates** tab.

3. Click **Create Template**.

4. Enter a **Template Name** to identify this template.

5. Enter the **Title** and **Message** content.

6. Click **Create**.

{end_tabs}

### Use a template

{start_tabs}

{tab|desktop-web}

1. Go to **Organization settings** > **Admin Notifications** > **Templates**.

2. Find the template you want to use.

3. Click **Use**.

4. The notification composer opens with the template content pre-filled.

5. Modify the content if needed.

6. Select recipients and click **Send**.

{end_tabs}

### Edit or delete a template

{start_tabs}

{tab|desktop-web}

1. Go to **Organization settings** > **Admin Notifications** > **Templates**.

2. Find the template you want to modify.

3. Click **Edit** to modify the template, or **Delete** to remove it.

{end_tabs}

## Notification delivery

Admin notifications are sent as direct messages from the administrator to recipients. Recipients will:

- See the notification in their inbox
- Receive desktop/mobile notifications (based on their settings)
- Be able to reply or react to the notification

### Delivery tracking

The admin notifications interface shows delivery statistics:

- **Total**: Number of recipients
- **Sent**: Successfully sent messages
- **Delivered**: Confirmed deliveries
- **Failed**: Failed delivery attempts (with error messages)
- **Read**: Recipients who have opened the notification

## Best practices

- **Use clear titles**: Help recipients understand the importance at a glance
- **Be concise**: Keep messages focused and actionable
- **Use templates**: Save time with common announcements
- **Target carefully**: Send to specific groups when possible to avoid notification fatigue
- **Include action items**: Make it clear what recipients should do
- **Follow up**: Check delivery statistics to ensure important messages were received

## Examples

### System maintenance announcement

```
Title: Scheduled Maintenance - Sunday 2 AM
Message: 
We will be performing scheduled maintenance this Sunday at 2:00 AM UTC.
The system will be unavailable for approximately 30 minutes.

- **Start**: Sunday, January 15, 2:00 AM UTC
- **Duration**: ~30 minutes
- **Impact**: All services will be temporarily unavailable

Please save any work before this time. Thank you for your understanding!
```

### Policy update

```
Title: Updated Privacy Policy
Message:
We've updated our privacy policy to improve transparency and comply with new regulations.

**What's new:**
- Enhanced data protection measures
- Clearer explanation of data usage
- New user rights and controls

📖 [Read the full policy](/policies/privacy)

These changes take effect on February 1st. Please review at your convenience.
```

### Team announcement

```
Title: Welcome Our New Team Members!
Message:
We're excited to welcome three new members to our engineering team:

- **Alice Johnson** - Senior Backend Engineer
- **Bob Smith** - Frontend Developer  
- **Carol Williams** - DevOps Engineer

Please join us in welcoming them to the team! 🎉

They'll be introducing themselves in #general this week.
```

## Related articles

* [Organization settings](/help/customize-organization-settings)
* [Message formatting](/help/format-your-message-using-markdown)
* [Direct messages](/help/direct-messages)
* [Organization administrators](/help/roles-and-permissions)

