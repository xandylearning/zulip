# LMS Integration Models
# External LMS models and Zulip mapping models will be defined here

from django.db import models


# =============================================================================
# CORE USER MODELS
# =============================================================================

class Students(models.Model):
    id = models.IntegerField(primary_key=True)
    username = models.TextField(unique=True)
    password_hash = models.TextField(blank=True, null=True)
    first_name = models.TextField(blank=True, null=True)
    last_name = models.TextField(blank=True, null=True)
    display_name = models.TextField(blank=True, null=True)
    email = models.TextField(blank=True, null=True)
    photo = models.TextField(blank=True, null=True)
    birth_date = models.TextField(blank=True, null=True)
    address1 = models.TextField(blank=True, null=True)
    address2 = models.TextField(blank=True, null=True)
    city = models.TextField(blank=True, null=True)
    zip = models.TextField(blank=True, null=True)
    state = models.TextField(blank=True, null=True)
    phone = models.TextField(blank=True, null=True)
    created = models.DateTimeField(blank=True, null=True)
    modified = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField()
    large_image = models.TextField(blank=True, null=True)
    medium_image = models.TextField(blank=True, null=True)
    medium_small_image = models.TextField(blank=True, null=True)
    small_image = models.TextField(blank=True, null=True)
    x_small_image = models.TextField(blank=True, null=True)
    mini_image = models.TextField(blank=True, null=True)
    batches_url = models.TextField(blank=True, null=True)
    gender_code = models.TextField(blank=True, null=True)
    gender = models.TextField(blank=True, null=True)
    state_code = models.TextField(blank=True, null=True)
    last_active_date = models.DateTimeField(blank=True, null=True)
    streak = models.IntegerField(blank=True, null=True)
    highest_streak = models.IntegerField(blank=True, null=True)
    last_parent_call = models.DateTimeField(blank=True, null=True)
    last_student_call = models.DateTimeField(blank=True, null=True)
    parent_number = models.TextField(blank=True, null=True)
    total_parent_call_count = models.IntegerField(blank=True, null=True)
    total_parent_call_verified = models.IntegerField(blank=True, null=True)
    total_student_call_count = models.IntegerField(blank=True, null=True)
    total_student_call_verified = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'students'


class Mentors(models.Model):
    username = models.TextField(unique=True)
    email = models.TextField(blank=True, null=True)
    first_name = models.TextField(blank=True, null=True)
    last_name = models.TextField(blank=True, null=True)
    display_name = models.TextField(blank=True, null=True)
    gender = models.TextField(blank=True, null=True)
    state = models.TextField(blank=True, null=True)
    created = models.DateTimeField()
    students_url = models.TextField(blank=True, null=True)
    students_count = models.IntegerField()
    user_id = models.IntegerField(unique=True, blank=True, null=True)
    hierarchy = models.TextField()  # This field type is a guess.
    supervisor_email = models.TextField(blank=True, null=True)
    supervisor = models.ForeignKey('self', models.DO_NOTHING, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'mentors'


# =============================================================================
# COURSE STRUCTURE MODELS
# =============================================================================

class Courses(models.Model):
    title = models.TextField()
    slug = models.TextField(unique=True)
    description = models.TextField(blank=True, null=True)
    image_url = models.TextField(blank=True, null=True)
    is_public = models.BooleanField(blank=True, null=True)
    created = models.DateTimeField(blank=True, null=True)
    modified = models.DateTimeField(blank=True, null=True)
    enable_progressive_lock = models.BooleanField(blank=True, null=True)
    order_index = models.IntegerField(blank=True, null=True)
    chapters_count = models.IntegerField()
    contents_count = models.IntegerField()
    exams_count = models.IntegerField()
    videos_count = models.IntegerField()
    attachments_count = models.IntegerField()
    html_contents_count = models.IntegerField()
    max_allowed_views_per_video = models.IntegerField(blank=True, null=True)
    max_allowed_watch_minutes = models.IntegerField(blank=True, null=True)
    created_by = models.IntegerField(blank=True, null=True)
    video_conferences_count = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'courses'


class Chapters(models.Model):
    id = models.IntegerField(primary_key=True)
    order = models.IntegerField()
    name = models.TextField()
    description = models.TextField(blank=True, null=True)
    image = models.TextField(blank=True, null=True)
    slug = models.TextField(unique=True)
    created = models.DateTimeField()
    modified = models.DateTimeField()
    required_trophy_count = models.IntegerField()
    course = models.ForeignKey('Courses', models.DO_NOTHING)
    parent = models.ForeignKey('self', models.DO_NOTHING, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'chapters'


class Chaptercontent(models.Model):
    id = models.IntegerField(primary_key=True)
    order = models.IntegerField()
    title = models.TextField()
    free_preview = models.BooleanField()
    url = models.TextField()
    modified = models.DateTimeField()
    start = models.DateTimeField()
    end = models.DateTimeField(blank=True, null=True)
    content_type = models.TextField()
    description = models.TextField(blank=True, null=True)
    html_content = models.TextField(blank=True, null=True)
    course_url = models.TextField()
    cover_image = models.TextField()
    cover_image_medium = models.TextField()
    cover_image_small = models.TextField()
    tags = models.TextField(blank=True, null=True)  # This field type is a guess.
    examid = models.ForeignKey('Exams', models.DO_NOTHING, db_column='examId', blank=True, null=True)  # Field name made lowercase.
    videoid = models.ForeignKey('Videos', models.DO_NOTHING, db_column='videoId', blank=True, null=True)  # Field name made lowercase.
    attachmentid = models.ForeignKey('Attachments', models.DO_NOTHING, db_column='attachmentId', blank=True, null=True)  # Field name made lowercase.
    course = models.ForeignKey('Courses', models.DO_NOTHING, blank=True, null=True)
    video_conference = models.ForeignKey('VideoConferences', models.DO_NOTHING, blank=True, null=True)
    live_stream = models.ForeignKey('LiveStreams', models.DO_NOTHING, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'ChapterContent'


# =============================================================================
# CONTENT MODELS
# =============================================================================

class Videos(models.Model):
    id = models.IntegerField(primary_key=True)
    title = models.TextField()
    url = models.TextField()
    description = models.TextField(blank=True, null=True)
    duration = models.TextField(blank=True, null=True)
    required_watch_duration = models.DecimalField(max_digits=10, decimal_places=4, blank=True, null=True)
    is_domain_restricted = models.BooleanField()
    embed_code = models.TextField(blank=True, null=True)
    course_title = models.TextField(blank=True, null=True)
    chapter_name = models.TextField(blank=True, null=True)
    content_created_date = models.DateTimeField(blank=True, null=True)
    totalduration = models.IntegerField(db_column='totalDuration', blank=True, null=True)  # Field name made lowercase.
    transcoded_video = models.JSONField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'videos'


class Exams(models.Model):
    id = models.IntegerField(primary_key=True)
    slug = models.TextField(unique=True)
    title = models.TextField()
    description = models.TextField(blank=True, null=True)
    duration = models.IntegerField()
    enable_ranks = models.BooleanField(blank=True, null=True)
    mark_per_question = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    negative_marks = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    number_of_questions = models.IntegerField()
    pass_percentage = models.IntegerField(blank=True, null=True)
    published = models.BooleanField(blank=True, null=True)
    show_score = models.BooleanField(blank=True, null=True)
    show_percentile = models.BooleanField(blank=True, null=True)
    show_pass_or_fail = models.BooleanField(blank=True, null=True)
    total_marks = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    start_date = models.DateTimeField(blank=True, null=True)
    end_date = models.DateTimeField(blank=True, null=True)
    created = models.DateTimeField()
    modified = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'exams'


class Attachments(models.Model):
    id = models.IntegerField(primary_key=True)
    title = models.TextField()
    attachment_url = models.TextField()
    description = models.TextField(blank=True, null=True)
    is_renderable = models.BooleanField()
    created = models.DateTimeField()
    modified = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'attachments'


class LiveStreams(models.Model):
    title = models.TextField()
    stream_url = models.TextField(blank=True, null=True)
    duration = models.IntegerField(blank=True, null=True)
    show_recorded_video = models.BooleanField()
    status = models.TextField()
    chat_embed_url = models.TextField(blank=True, null=True)
    created = models.DateTimeField()
    modified = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'live_streams'


class VideoConferences(models.Model):
    id = models.IntegerField(primary_key=True)
    title = models.TextField()
    conference_id = models.TextField()
    start = models.DateTimeField()
    duration = models.IntegerField()
    provider = models.TextField()
    join_url = models.TextField()
    password = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    access_token = models.TextField(blank=True, null=True)
    created = models.DateTimeField()
    modified = models.DateTimeField(blank=True, null=True)
    has_recording_expired = models.BooleanField()
    show_recorded_video = models.BooleanField()
    state = models.TextField()

    class Meta:
        managed = False
        db_table = 'video_conferences'


# =============================================================================
# EXAM STRUCTURE MODELS
# =============================================================================

class Sections(models.Model):
    order = models.IntegerField()
    name = models.TextField()

    class Meta:
        managed = False
        db_table = 'sections'


class ExamQuestions(models.Model):
    questionid = models.IntegerField(db_column='questionId')  # Field name made lowercase.
    sectionid = models.ForeignKey('Sections', models.DO_NOTHING, db_column='sectionId')  # Field name made lowercase.
    questionhtml = models.TextField(db_column='questionHtml')  # Field name made lowercase.
    explanationhtml = models.TextField(db_column='explanationHtml', blank=True, null=True)  # Field name made lowercase.
    reference = models.TextField(blank=True, null=True)
    type = models.TextField()
    marks = models.FloatField()
    negativemarks = models.FloatField(db_column='negativeMarks')  # Field name made lowercase.
    partialmarks = models.FloatField(db_column='partialMarks', blank=True, null=True)  # Field name made lowercase.
    direction = models.TextField(blank=True, null=True)
    order = models.IntegerField()
    isbonus = models.BooleanField(db_column='isBonus')  # Field name made lowercase.
    examid = models.IntegerField(db_column='examId')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'exam_questions'


class Answers(models.Model):
    examquestionid = models.ForeignKey('ExamQuestions', models.DO_NOTHING, db_column='examQuestionId')  # Field name made lowercase.
    texthtml = models.TextField(db_column='textHtml')  # Field name made lowercase.
    iscorrect = models.BooleanField(db_column='isCorrect')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'answers'


# =============================================================================
# BATCH AND ORGANIZATION MODELS
# =============================================================================

class Batches(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.TextField(blank=True, null=True)
    url = models.TextField(blank=True, null=True)
    created = models.DateTimeField(blank=True, null=True)
    modified = models.DateTimeField(blank=True, null=True)
    is_local = models.BooleanField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'batches'


# =============================================================================
# ACTIVITY AND PROGRESS MODELS
# =============================================================================

class Attempts(models.Model):
    id = models.IntegerField(primary_key=True)
    date = models.DateTimeField(blank=True, null=True)
    exam = models.ForeignKey('Exams', models.DO_NOTHING, blank=True, null=True)
    user = models.ForeignKey('Students', models.DO_NOTHING, blank=True, null=True)
    email = models.TextField(blank=True, null=True)
    name = models.TextField(blank=True, null=True)
    phone = models.TextField(blank=True, null=True)
    correct_answers_count = models.IntegerField(blank=True, null=True)
    incorrect_answers_count = models.IntegerField(blank=True, null=True)
    unanswered_count = models.IntegerField(blank=True, null=True)
    score = models.IntegerField(blank=True, null=True)
    percentage = models.IntegerField(blank=True, null=True)
    percentile = models.FloatField(blank=True, null=True)
    time_taken = models.TextField(blank=True, null=True)
    remaining_time = models.TextField(blank=True, null=True)
    result = models.TextField(blank=True, null=True)
    state = models.TextField(blank=True, null=True)
    last_started_time = models.DateTimeField(blank=True, null=True)
    last_answer_updated_time = models.DateTimeField(blank=True, null=True)
    speed = models.IntegerField(blank=True, null=True)
    exam_url = models.TextField(blank=True, null=True)
    user_url = models.TextField(blank=True, null=True)
    username = models.TextField(blank=True, null=True)
    review_pdf_url = models.TextField(blank=True, null=True)
    institute_attempt_id = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'attempts'


class AttemptSections(models.Model):
    id = models.IntegerField(primary_key=True)
    order = models.IntegerField(blank=True, null=True)
    section_id = models.IntegerField(blank=True, null=True)
    time_taken = models.TextField(blank=True, null=True)
    correct_answers_count = models.IntegerField(blank=True, null=True)
    incorrect_answers_count = models.IntegerField(blank=True, null=True)
    unanswered_count = models.IntegerField(blank=True, null=True)
    score = models.TextField(blank=True, null=True)
    attempt = models.ForeignKey('Attempts', models.DO_NOTHING, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'attempt_sections'


class ContentAttempts(models.Model):
    id = models.IntegerField(primary_key=True)
    user = models.ForeignKey('Students', models.DO_NOTHING)
    course = models.ForeignKey('Courses', models.DO_NOTHING)
    chapter = models.ForeignKey(Chapters, models.DO_NOTHING)
    chapter_content = models.ForeignKey(Chaptercontent, models.DO_NOTHING)
    content_type = models.TextField()
    state = models.TextField()
    remaining_time = models.TextField(blank=True, null=True)
    assessment = models.ForeignKey(Attempts, models.DO_NOTHING, blank=True, null=True)
    user_video_conference = models.ForeignKey('UserConferences', models.DO_NOTHING, blank=True, null=True)
    user_video = models.ForeignKey('UserVideos', models.DO_NOTHING, blank=True, null=True)
    user_live_stream = models.ForeignKey('UserLiveStreams', models.DO_NOTHING, blank=True, null=True)
    user_content_id = models.IntegerField(blank=True, null=True)
    user_attachment = models.ForeignKey(Attachments, models.DO_NOTHING, blank=True, null=True)
    correct_answers_count = models.IntegerField(blank=True, null=True)
    incorrect_answers_count = models.IntegerField(blank=True, null=True)
    created = models.DateTimeField()
    completed_on = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'content_attempts'


class UserVideos(models.Model):
    id = models.IntegerField(primary_key=True)
    video = models.ForeignKey('Videos', models.DO_NOTHING)
    user = models.ForeignKey('Students', models.DO_NOTHING)
    created = models.DateTimeField()
    watched_percentage = models.IntegerField()
    remaining_duration = models.TextField(blank=True, null=True)
    state = models.TextField()
    is_live_class_recording = models.BooleanField()

    class Meta:
        managed = False
        db_table = 'user_videos'


class UserVideoProgress(models.Model):
    id = models.IntegerField(primary_key=True)
    user = models.ForeignKey('Students', models.DO_NOTHING)
    video = models.ForeignKey('Videos', models.DO_NOTHING)
    created = models.DateTimeField(blank=True, null=True)
    watched_percentage = models.DecimalField(max_digits=65, decimal_places=30, blank=True, null=True)
    watchedduration = models.IntegerField(db_column='watchedDuration', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'user_video_progress'


class UserConferences(models.Model):
    user = models.ForeignKey(Students, models.DO_NOTHING)
    conference = models.ForeignKey('VideoConferences', models.DO_NOTHING)
    join_time = models.DateTimeField(blank=True, null=True)
    leave_time = models.DateTimeField(blank=True, null=True)
    duration = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'user_conferences'


class UserLiveStreams(models.Model):
    id = models.IntegerField(primary_key=True)
    user_id = models.IntegerField()
    live_stream = models.ForeignKey(LiveStreams, models.DO_NOTHING)
    created = models.DateTimeField()
    modified = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'user_live_streams'


class UserAnswers(models.Model):
    adaptivequestionpoolid = models.IntegerField(db_column='adaptiveQuestionPoolId', blank=True, null=True)  # Field name made lowercase.
    examquestionid = models.ForeignKey(ExamQuestions, models.DO_NOTHING, db_column='examQuestionId')  # Field name made lowercase.
    attemptsectionid = models.ForeignKey('UserAnswerAttemptSections', models.DO_NOTHING, db_column='attemptSectionId')  # Field name made lowercase.
    selectedanswers = models.TextField(db_column='selectedAnswers', blank=True, null=True)  # Field name made lowercase. This field type is a guess.
    userresponse = models.TextField(db_column='userResponse', blank=True, null=True)  # Field name made lowercase.
    result = models.TextField()
    duration = models.IntegerField()
    review = models.BooleanField(blank=True, null=True)
    guessed = models.BooleanField(blank=True, null=True)
    attemptid = models.ForeignKey(Attempts, models.DO_NOTHING, db_column='attemptId', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'user_answers'


class UserAnswerAttemptSections(models.Model):
    order = models.IntegerField()
    sectionid = models.ForeignKey(Sections, models.DO_NOTHING, db_column='sectionId')  # Field name made lowercase.
    sectionname = models.TextField(db_column='sectionName')  # Field name made lowercase.
    timetaken = models.TextField(db_column='timeTaken')  # Field name made lowercase.
    correctanswerscount = models.IntegerField(db_column='correctAnswersCount')  # Field name made lowercase.
    incorrectanswerscount = models.IntegerField(db_column='incorrectAnswersCount')  # Field name made lowercase.
    unansweredcount = models.IntegerField(db_column='unansweredCount')  # Field name made lowercase.
    score = models.FloatField()
    state = models.TextField()
    remainingtime = models.TextField(db_column='remainingTime', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'user_answer_attempt_sections'


# =============================================================================
# RELATIONSHIP/JUNCTION MODELS (Many-to-Many)
# =============================================================================

class Batchtostudent(models.Model):
    id = models.AutoField(primary_key=True)
    a = models.ForeignKey('Batches', models.DO_NOTHING, db_column='A')  # Field name made lowercase.
    b = models.ForeignKey('Students', models.DO_NOTHING, db_column='B')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = '_BatchToStudent'
        unique_together = (('a', 'b'),)


class Coursebatch(models.Model):
    id = models.AutoField(primary_key=True)
    a = models.ForeignKey('Batches', models.DO_NOTHING, db_column='A')  # Field name made lowercase.
    b = models.ForeignKey('Courses', models.DO_NOTHING, db_column='B')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = '_CourseBatch'
        unique_together = (('a', 'b'),)


class Examcourse(models.Model):
    id = models.AutoField(primary_key=True)
    a = models.ForeignKey('Courses', models.DO_NOTHING, db_column='A')  # Field name made lowercase.
    b = models.ForeignKey('Exams', models.DO_NOTHING, db_column='B')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = '_ExamCourse'
        unique_together = (('a', 'b'),)


class Mentortostudent(models.Model):
    id = models.AutoField(primary_key=True)
    a = models.ForeignKey('Mentors', models.DO_NOTHING, db_column='A')  # Field name made lowercase.
    b = models.ForeignKey('Students', models.DO_NOTHING, db_column='B')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = '_MentorToStudent'
        unique_together = (('a', 'b'),)


class Chaptertocontent(models.Model):
    id = models.AutoField(primary_key=True)
    chapterid = models.ForeignKey('Chapters', models.DO_NOTHING, db_column='chapterId')  # Field name made lowercase.
    contentid = models.ForeignKey(Chaptercontent, models.DO_NOTHING, db_column='contentId')  # Field name made lowercase.
    order = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'ChapterToContent'
        unique_together = (('chapterid', 'contentid'),)


# =============================================================================
# ANALYTICS AND TRACKING MODELS
# =============================================================================

class StudentActivities(models.Model):
    student_id = models.CharField(max_length=50, blank=True, null=True)
    timestamp = models.DateTimeField()
    current_streak = models.IntegerField(blank=True, null=True)
    highest_streak = models.IntegerField(blank=True, null=True)
    last_completed_date = models.CharField(max_length=50, blank=True, null=True)
    total_videos_watched = models.IntegerField(blank=True, null=True)
    total_exams_taken = models.IntegerField(blank=True, null=True)
    total_attachments_downloaded = models.IntegerField(blank=True, null=True)
    total_video_conferences = models.IntegerField(blank=True, null=True)
    fetch_date = models.DateField()

    class Meta:
        managed = False
        db_table = 'student_activities'
        unique_together = (('student_id', 'fetch_date'),)


class StudentActivityDates(models.Model):
    id = models.AutoField(primary_key=True)
    student_id = models.CharField(max_length=50)
    activity_date = models.DateField()

    class Meta:
        managed = False
        db_table = 'student_activity_dates'
        unique_together = (('student_id', 'activity_date'),)


class DailySummary(models.Model):
    fetch_date = models.DateField(primary_key=True)
    timestamp = models.DateTimeField()
    total_students_fetched = models.IntegerField(blank=True, null=True)
    execution_time_seconds = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'daily_summary'


class DifficultyLevelStats(models.Model):
    difficulty_level = models.TextField(blank=True, null=True)
    correct_answers_count = models.IntegerField(blank=True, null=True)
    incorrect_answers_count = models.IntegerField(blank=True, null=True)
    partial_correct_answers_count = models.IntegerField(blank=True, null=True)
    unanswered_count = models.IntegerField(blank=True, null=True)
    total_count = models.IntegerField(blank=True, null=True)
    attempt = models.ForeignKey(Attempts, models.DO_NOTHING, blank=True, null=True)
    attemptsectionid = models.OneToOneField('UserAnswerAttemptSections', models.DO_NOTHING, db_column='attemptSectionId', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'difficulty_level_stats'


class SubjectStats(models.Model):
    subject_id = models.IntegerField(blank=True, null=True)
    subject_name = models.TextField(blank=True, null=True)
    total_count = models.IntegerField(blank=True, null=True)
    correct_answers_count = models.IntegerField(blank=True, null=True)
    unanswered_count = models.IntegerField(blank=True, null=True)
    incorrect_answers_count = models.IntegerField(blank=True, null=True)
    parent_subject_id = models.IntegerField(blank=True, null=True)
    is_leaf = models.BooleanField(blank=True, null=True)
    score = models.TextField(blank=True, null=True)
    partial_correct_answers_count = models.IntegerField(blank=True, null=True)
    attempt = models.ForeignKey(Attempts, models.DO_NOTHING, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'subject_stats'


# =============================================================================
# SCHEDULING MODELS
# =============================================================================

class ClassSchedule(models.Model):
    date = models.DateField()
    day = models.CharField(max_length=20, blank=True, null=True)
    grade = models.IntegerField()
    board = models.TextField()  # This field type is a guess.
    section = models.CharField(max_length=10, blank=True, null=True)
    subject = models.CharField(max_length=100)
    chapter = models.CharField(max_length=200, blank=True, null=True)
    content = models.TextField(blank=True, null=True)
    duration = models.CharField(max_length=50, blank=True, null=True)
    sessiontype = models.TextField(db_column='sessionType')  # Field name made lowercase. This field type is a guess.
    createdat = models.DateTimeField(db_column='createdAt')  # Field name made lowercase.
    updatedat = models.DateTimeField(db_column='updatedAt')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'class_schedule'
        unique_together = (('date', 'grade', 'board', 'section', 'subject'),)


class FacultySchedule(models.Model):
    date = models.DateField()
    facultyname = models.CharField(db_column='facultyName', max_length=100)  # Field name made lowercase.
    sessiontype = models.CharField(db_column='sessionType', max_length=50, blank=True, null=True)  # Field name made lowercase.
    subcolumn = models.CharField(db_column='subColumn', max_length=50, blank=True, null=True)  # Field name made lowercase.
    timeslot = models.CharField(db_column='timeSlot', max_length=50, blank=True, null=True)  # Field name made lowercase.
    activitytype = models.CharField(db_column='activityType', max_length=50, blank=True, null=True)  # Field name made lowercase.
    details = models.TextField()
    createdat = models.DateTimeField(db_column='createdAt')  # Field name made lowercase.
    updatedat = models.DateTimeField(db_column='updatedAt')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'faculty_schedule'
        unique_together = (('date', 'facultyname', 'subcolumn', 'details'),)


# =============================================================================
# MISCELLANEOUS MODELS
# =============================================================================

class AdaptiveQuestionPools(models.Model):

    class Meta:
        managed = False
        db_table = 'adaptive_question_pools'


class Bookmarks(models.Model):

    class Meta:
        managed = False
        db_table = 'bookmarks'


# =============================================================================
# LMS EVENT MODELS (STORED IN ZULIP DATABASE)
# =============================================================================

class LMSActivityEvent(models.Model):
    """
    Core event storage table for LMS activities.
    Stored in Zulip's default database for AI processing and notifications.
    """
    
    # Event identification
    event_id = models.AutoField(primary_key=True)
    event_type = models.CharField(
        max_length=50,
        choices=[
            ('exam_started', 'Exam Started'),
            ('exam_completed', 'Exam Completed'),
            ('exam_failed', 'Exam Failed'),
            ('exam_passed', 'Exam Passed'),
            ('content_started', 'Content Started'),
            ('content_completed', 'Content Completed'),
            ('content_watched', 'Content Watched'),
        ]
    )
    
    # Student information (from LMS)
    student_id = models.IntegerField(help_text="Student ID from LMS database")
    student_username = models.CharField(max_length=255, blank=True, null=True)
    
    # Mentor information (from LMS)
    mentor_id = models.IntegerField(blank=True, null=True, help_text="Mentor ID from LMS database")
    mentor_username = models.CharField(max_length=255, blank=True, null=True)
    
    # Activity details
    activity_id = models.IntegerField(help_text="Exam or content ID from LMS")
    activity_title = models.CharField(max_length=500, blank=True, null=True)
    activity_metadata = models.JSONField(
        blank=True, 
        null=True,
        help_text="Additional data like scores, percentage, duration, etc."
    )
    
    # Timestamps
    timestamp = models.DateTimeField(help_text="When the activity occurred in LMS")
    created_at = models.DateTimeField(auto_now_add=True)
    
    # AI processing flag
    processed_for_ai = models.BooleanField(
        default=False,
        help_text="Whether this event has been processed for AI analysis"
    )
    
    # Optional Zulip user linking
    zulip_user_id = models.IntegerField(
        blank=True, 
        null=True,
        help_text="Zulip UserProfile ID if student has Zulip account"
    )
    
    class Meta:
        managed = True
        db_table = 'lms_activity_events'
        indexes = [
            models.Index(fields=['student_id']),
            models.Index(fields=['event_type']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['processed_for_ai']),
        ]
        ordering = ['-timestamp']


class LMSEventLog(models.Model):
    """
    Event processing audit trail.
    Tracks notification status and errors for each event.
    """
    
    event = models.OneToOneField(
        LMSActivityEvent,
        on_delete=models.CASCADE,
        primary_key=True,
        help_text="The LMS activity event this log entry refers to"
    )
    
    # Notification tracking
    notification_sent = models.BooleanField(default=False)
    notification_message_id = models.IntegerField(
        blank=True, 
        null=True,
        help_text="Zulip message ID of the notification sent to mentor"
    )
    
    # Error handling
    error_message = models.TextField(
        blank=True, 
        null=True,
        help_text="Error details if processing failed"
    )
    
    # Processing timestamp
    processed_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        managed = True
        db_table = 'lms_event_logs'
        ordering = ['-processed_at']