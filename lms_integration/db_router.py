# LMS Database Router
# Routes LMS model queries to lms_db database (read-only)
# Zulip-managed models (admin config, sync history, logs, user mappings) 
# are stored in Zulip's default database and NEVER touch the LMS database

class LMSRouter:
    """
    Database router for LMS integration.
    
    - External LMS models (Students, Mentors, Courses, etc.) are read-only 
      and routed to 'lms_db' database
    - Zulip-managed models (LMSIntegrationConfig, LMSSyncHistory, LMSAdminLog, 
      LMSUserMapping, LMSActivityEvent, LMSEventLog) are stored in Zulip's 
      default database and never touch the LMS database
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
    
    # Zulip-managed models that should use the default database (Zulip DB)
    # These models are created and managed by Zulip, stored in Zulip's database
    zulip_managed_models = {
        # Activity tracking models
        'LMSActivityEvent', 'LMSEventLog',
        # Admin configuration models (stored in Zulip DB, not LMS DB)
        'LMSIntegrationConfig', 'LMSSyncHistory', 'LMSAdminLog', 'LMSUserMapping'
    }
    
    def db_for_read(self, model, **hints):
        """Route read operations - LMS models to lms_db, Zulip models to default DB"""
        if model.__name__ in self.lms_models:
            return 'lms_db'  # External LMS models (read-only)
        if model.__name__ in self.zulip_managed_models:
            return 'default'  # Zulip-managed models in Zulip database
        return None  # Other models use default database
    
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
