# LMS Database Router
# Routes LMS model queries to lms_db database

class LMSRouter:
    """
    Database router for LMS integration.
    Routes LMS external models to lms_db database.
    """
    
    # All LMS models that should use the lms_db database
    lms_models = {
        # Core User Models
        'Students', 'Mentors',
        
        # Course Structure Models
        'Courses', 'Chapters', 'Chaptercontent',
        
        # Content Models
        'Videos', 'Exams', 'Attachments', 'LiveStreams', 'VideoConferences',
        
        # Exam Structure Models
        'Sections', 'ExamQuestions', 'Answers',
        
        # Batch and Organization Models
        'Batches',
        
        # Activity and Progress Models
        'Attempts', 'AttemptSections', 'ContentAttempts', 'UserVideos', 
        'UserVideoProgress', 'UserConferences', 'UserLiveStreams', 
        'UserAnswers', 'UserAnswerAttemptSections',
        
        # Relationship/Junction Models
        'Batchtostudent', 'Coursebatch', 'Examcourse', 'Mentortostudent', 'Chaptertocontent',
        
        # Analytics and Tracking Models
        'StudentActivities', 'StudentActivityDates', 'DailySummary', 
        'DifficultyLevelStats', 'SubjectStats',
        
        # Scheduling Models
        'ClassSchedule', 'FacultySchedule',
        
        # Miscellaneous Models
        'AdaptiveQuestionPools', 'Bookmarks'
    }
    
    # Zulip-managed models that should use the default database
    zulip_managed_models = {
        'LMSActivityEvent', 'LMSEventLog'
    }
    
    def db_for_read(self, model, **hints):
        """Route read operations for LMS models to lms_db"""
        if model.__name__ in self.lms_models:
            return 'lms_db'
        return None
    
    def db_for_write(self, model, **hints):
        """Route write operations - LMS models are read-only, Zulip models use default DB"""
        if model.__name__ in self.lms_models:
            return None  # Read-only access to external LMS database
        if model.__name__ in self.zulip_managed_models:
            return 'default'  # Zulip-managed models use default database
        return None
    
    def allow_relation(self, obj1, obj2, **hints):
        """Allow relations between models in the same database"""
        # Allow relations between LMS models (same database)
        if (obj1._meta.model.__name__ in self.lms_models and 
            obj2._meta.model.__name__ in self.lms_models):
            return True
        return None
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Control which migrations are allowed"""
        if app_label == 'lms_integration':
            # Block migrations for all LMS models (they're managed=False)
            if model_name in self.lms_models:
                return False  # External models don't need migrations
            # Allow migrations for Zulip-managed models in default database
            if model_name in self.zulip_managed_models:
                return db == 'default'
            # Allow migrations for other lms_integration models in default database
            return db == 'default'
        return None
