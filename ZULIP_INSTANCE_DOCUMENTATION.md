# Zulip Instance Documentation

## Overview

This document provides comprehensive documentation for the customized Zulip instance, including all modifications, role changes, AI integrations, and deployment configurations.

## Instance Information

- **Zulip Version**: 12.0-dev+git (Development version)
- **API Feature Level**: 425
- **Provision Version**: 343.0
- **Branch**: version.0.0.1
- **Base Path**: `/Users/straxs/Work/zulip`

## Major Customizations Implemented

### 1. AI Agent System Integration

#### Overview
A comprehensive AI-powered messaging system has been integrated using LangGraph multi-agent workflows with Portkey AI gateway integration.

#### Key Features
- **Event-Driven Architecture**: Asynchronous AI conversation processing
- **Multi-Agent Workflows**: Style analysis, context analysis, response generation
- **Portkey Integration**: Enterprise-grade LLM gateway with observability
- **Mentor-Student Communication**: AI-powered mentor response system

#### Configuration Files
- `zproject/ai_agent_settings.py` - Core AI agent configuration
- `docs/production/ai-agent-environment-variables.md` - Environment variables guide
- `docs/subsystems/ai-messaging-integration.md` - Technical architecture

#### Environment Variables
```bash
# Core Configuration
USE_LANGGRAPH_AGENTS=true
PORTKEY_API_KEY=your_portkey_api_key_here
AI_MENTOR_MODEL=gpt-4
AI_MENTOR_TEMPERATURE=0.7
AI_MENTOR_MAX_TOKENS=1000

# Decision Thresholds
AI_MENTOR_MIN_ABSENCE_MINUTES=240  # 4 hours
AI_MENTOR_MAX_DAILY_RESPONSES=3
AI_MENTOR_URGENCY_THRESHOLD=0.7
AI_MENTOR_CONFIDENCE_THRESHOLD=0.6

# State Management
AI_AGENT_STATE_DB_PATH=/var/lib/zulip/ai_agent_state.db
```

#### Implementation Files
- `zerver/lib/ai_agent_core.py` - Core AI agent functionality
- `zerver/event_listeners/ai_mentor.py` - Event-driven AI processing
- `zerver/actions/ai_mentor_events.py` - AI event management
- `scripts/install-ai-dependencies` - AI dependency installation

### 2. Custom Role System

#### Overview
The default Zulip role system has been completely replaced with an educational institution-focused role hierarchy.

#### New Role Hierarchy

| Role | Code | Description | Permissions |
|------|------|-------------|-------------|
| Owner | 100 | Realm owner | Full administrative access |
| Administrator | 200 | Realm administrator | Administrative access |
| Faculty | 450 | Faculty members | Full member access |
| Student | 500 | Students | Limited access |
| Parent | 550 | Parents | Limited access |
| Mentor | 580 | Mentors | Full member access |

#### Communication Restrictions
- **Students** cannot communicate with other students
- **Parents** cannot communicate with other parents
- **Parents** can chat only with mentors, faculty, and students
- **Students** can chat only with mentors
- **Mentors** can chat with parents, faculty, and students

#### Implementation Files
- `zerver/models/users.py` - User model with new roles
- `zerver/models/groups.py` - System groups for new roles
- `zerver/actions/message_send.py` - Communication restriction logic
- `dev-docs/CUSTOM_ROLES_IMPLEMENTATION.md` - Detailed implementation guide

#### Database Migrations
- `zerver/migrations/9999_add_custom_roles.py` - Creates new role groups
- `zerver/migrations/10000_remove_unwanted_roles.py` - Removes old roles
- `zerver/migrations/0001_squashed_0569.py` - Updates default role

### 3. Python Dependencies Management

#### Modern Dependency Management
The instance uses `uv` (modern Python package manager) instead of traditional pip/requirements.txt:

- **Main Configuration**: `pyproject.toml`
- **Lock File**: `uv.lock`
- **Dependency Groups**: `prod`, `docs`, `dev`

#### AI Dependencies
Additional AI-specific dependencies are managed through:
- `scripts/install-ai-dependencies` - Installs LangGraph, Portkey, and AI packages
- Dependencies include: `langgraph`, `portkey-ai`, `langsmith`, `openai`, etc.

#### Virtual Environment Structure
- **Location**: `{deploy_path}/.venv/`
- **Activation**: Handled by `scripts/lib/setup_path.py`
- **Installation**: Managed by `scripts/lib/create-production-venv`

### 4. Deployment and Installation

#### Installation Scripts
- `scripts/setup/install` - Main installation wrapper
- `scripts/lib/install` - Core installation logic
- `scripts/lib/create-production-venv` - Virtual environment creation
- `scripts/lib/setup_venv.py` - System dependencies

#### Upgrade Scripts
- `scripts/lib/upgrade-zulip` - Main upgrade script
- `scripts/lib/upgrade-zulip-from-git` - Git-based upgrades
- `scripts/lib/upgrade-zulip-stage-3` - Final upgrade stage

#### Deployment Paths
- **Production**: `/home/zulip/deployments/current/`
- **Virtual Environment**: `{deploy_path}/.venv/`
- **AI State**: `/var/lib/zulip/ai_agent_state.db`

## Configuration Files

### Core Settings
- `zproject/dev_settings.py` - Development settings
- `zproject/ai_agent_settings.py` - AI agent configuration
- `zproject/computed_settings.py` - Computed settings integration

### Documentation
- `docs/production/ai-agent-environment-variables.md` - AI configuration guide
- `docs/subsystems/ai-messaging-integration.md` - AI architecture
- `dev-docs/CUSTOM_ROLES_IMPLEMENTATION.md` - Role system documentation

### API Documentation
- `api_docs/roles-and-permissions.md` - Updated role documentation
- `help/user-roles.md` - User role help

## Key Features and Capabilities

### 1. AI-Powered Communication
- **Intelligent Response Generation**: AI agents analyze mentor styles and generate contextual responses
- **Event-Driven Processing**: Asynchronous AI conversation handling
- **Multi-Agent Workflows**: Style analysis, context analysis, response generation
- **Portkey Integration**: Enterprise-grade LLM gateway with observability

### 2. Educational Role System
- **Custom Role Hierarchy**: Owner, Administrator, Faculty, Student, Parent, Mentor
- **Communication Restrictions**: Controlled communication between different role types
- **Educational Focus**: Designed specifically for educational institutions

### 3. Modern Python Management
- **UV Package Manager**: Fast, modern Python dependency management
- **Dependency Groups**: Separate configurations for production, development, and documentation
- **Virtual Environment**: Isolated Python environment for all dependencies

### 4. Production-Ready Deployment
- **Automated Installation**: Comprehensive installation and upgrade scripts
- **Configuration Management**: Environment-based configuration system
- **Monitoring and Logging**: Built-in monitoring for AI agents and system health

## Environment Setup

### Development Environment
```bash
# AI Agent Configuration
export USE_LANGGRAPH_AGENTS=true
export AI_MENTOR_MIN_ABSENCE_MINUTES=5
export AI_MENTOR_CONFIDENCE_THRESHOLD=0.3
export AI_MENTOR_URGENCY_THRESHOLD=0.3
export PORTKEY_API_KEY=test_key_for_development
```

### Production Environment
```bash
# Production AI Settings
export USE_LANGGRAPH_AGENTS=true
export AI_MENTOR_MIN_ABSENCE_MINUTES=240
export AI_MENTOR_CONFIDENCE_THRESHOLD=0.7
export AI_MENTOR_URGENCY_THRESHOLD=0.8
export PORTKEY_API_KEY=your_production_api_key
export AI_AGENT_STATE_DB_PATH=/var/lib/zulip/ai_agent_state.db
```

## Installation and Deployment

### Prerequisites
- Python 3.10+
- PostgreSQL
- Redis
- RabbitMQ
- Node.js (for frontend)

### Installation Process
1. **System Dependencies**: Install via `scripts/lib/setup_venv.py`
2. **Python Environment**: Create via `scripts/lib/create-production-venv`
3. **AI Dependencies**: Install via `scripts/install-ai-dependencies`
4. **Database Setup**: Initialize via `scripts/setup/initialize-database`
5. **Configuration**: Set environment variables and secrets

### Upgrade Process
1. **System Upgrade**: Run `scripts/lib/upgrade-zulip`
2. **Dependencies**: Update via `uv sync --frozen --only-group=prod`
3. **AI Dependencies**: Reinstall if needed
4. **Database Migrations**: Apply automatically during upgrade

## Monitoring and Maintenance

### AI Agent Monitoring
- **Logs**: Check `/var/log/zulip/django.log` for AI agent warnings
- **State Database**: Monitor `/var/lib/zulip/ai_agent_state.db`
- **Performance**: Track AI response times and success rates

### Role System Monitoring
- **User Roles**: Monitor role assignments and communication restrictions
- **System Groups**: Ensure proper group relationships
- **Database Integrity**: Check for role-related constraint violations

### System Health
- **Dependencies**: Monitor Python package versions
- **Virtual Environment**: Ensure proper isolation
- **Configuration**: Validate environment variables

## Troubleshooting

### Common Issues
1. **AI Agent Configuration**: Check environment variables and API keys
2. **Role System**: Verify user role assignments and communication restrictions
3. **Dependencies**: Ensure all Python packages are properly installed
4. **Database**: Check for migration issues and constraint violations

### Debug Commands
```bash
# Check AI agent configuration
python test_ai_integration.py

# Validate role system
python manage.py check

# Test dependencies
uv sync --frozen --only-group=prod
```

## Future Enhancements

### Planned Features
- **LMS Integration**: External student data integration
- **Advanced Analytics**: Enhanced AI agent performance monitoring
- **Role Customization**: Additional role types and permissions
- **API Extensions**: Enhanced API for AI agent interactions

### Maintenance Tasks
- **Regular Updates**: Keep dependencies current
- **Performance Monitoring**: Track AI agent performance
- **Security Updates**: Apply security patches promptly
- **Backup Management**: Regular database and configuration backups

## Support and Resources

### Documentation
- `docs/production/ai-agent-environment-variables.md` - AI configuration
- `docs/subsystems/ai-messaging-integration.md` - Technical architecture
- `dev-docs/CUSTOM_ROLES_IMPLEMENTATION.md` - Role system details

### Configuration Files
- `pyproject.toml` - Python dependencies
- `zproject/ai_agent_settings.py` - AI agent settings
- `scripts/install-ai-dependencies` - AI dependency installation

### Testing
- `test_ai_integration.py` - AI system testing
- `test_ai_mentor_event_fix.py` - AI mentor event testing
- `test_event_listeners_dev.sh` - Event listener testing

This documentation provides a comprehensive overview of the customized Zulip instance, including all modifications, configurations, and deployment procedures.
