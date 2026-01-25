(zulip-server) vagrant@991ef363f65b:/srv/zulip$ export LMS_DB_NAME=production_live
(zulip-server) vagrant@991ef363f65b:/srv/zulip$ export LMS_DB_PASSWORD="M8d&dxD7udSX@.HD"
(zulip-server) vagrant@991ef363f65b:/srv/zulip$ export LMS_USER=zulip_read_only
(zulip-server) vagrant@991ef363f65b:/srv/zulip$ export LMS_DB_HOST=34.47.243.199
(zulip-server) vagrant@991ef363f65b:/srv/zulip$ export LMS_DB_USER=zulip_read_only
(zulip-server) vagrant@991ef363f65b:/srv/zulip$ python manage.py shell -c "from lms_integration.models import Mentors; print(f'Mentors in LMS DB: {Mentors.objects.using(\"lms_db\").count()}')"
2026-01-08 07:40:34.644 INFO [] Zulip Calls Plugin initialized
161 objects imported automatically (use -v 2 for details).