# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Running the Development Server
```bash
./tools/run-dev
```
Starts the Django development server and webpack dev server for frontend assets.

### Testing
```bash
./tools/test-backend               # Run Django backend tests
./tools/test-js-with-node          # Run Node.js frontend tests
./tools/test-js-with-puppeteer     # Run frontend browser tests
./tools/test-all                   # Run all tests (comprehensive)
./tools/test-migrations            # Test database migrations
```

To run specific tests:
```bash
./tools/test-backend zerver.tests.test_messages  # Specific backend test module
./tools/test-js-with-node web/tests/user_events.test.js  # Specific frontend test
```

### Linting and Code Quality
```bash
./tools/lint                       # Run all linters (Ruff, ESLint, mypy, etc.)
ruff check                         # Python linting
ruff format                        # Python formatting
npm run lint                       # JavaScript/TypeScript linting
npm run prettier                   # JavaScript/TypeScript formatting
./tools/check-openapi              # Validate OpenAPI schema
./tools/check-templates            # Validate Django templates
mypy                               # Python type checking
```

### Database Operations
```bash
python manage.py migrate           # Apply database migrations
python manage.py makemigrations    # Create new migrations
python manage.py shell             # Django shell
python manage.py dbshell           # Database shell
```

### Build and Asset Management
```bash
npm run build                      # Build frontend assets for production
npm run build:dev                  # Build frontend assets for development
```

## Code Architecture

### Backend (Django)
- **zerver/**: Main Django app containing models, views, and business logic
  - `models.py`: Database models (User, Message, Stream, etc.)
  - `views/`: API endpoint implementations organized by feature
  - `lib/`: Core business logic and utilities
  - `actions/`: High-level operations that modify data
  - `event_listeners/`: Real-time event processing
- **zproject/**: Django project configuration and settings
- **zilencer/**: Analytics and mobile push notification handling
- **corporate/**: Billing and enterprise features
- **confirmation/**: Email confirmation system

### Frontend (TypeScript/jQuery)
- **web/src/**: TypeScript source files
  - Individual modules for different UI components and features
  - Uses jQuery for DOM manipulation and legacy compatibility
- **web/styles/**: PostCSS stylesheets
- **web/templates/**: Handlebars templates
- **static/**: Generated static assets

### Key Systems
- **Real-time messaging**: Tornado-based event system for live updates
- **API**: RESTful JSON API with comprehensive OpenAPI documentation
- **Authentication**: Supports multiple backends (LDAP, SAML, social auth)
- **Internationalization**: Full i18n support with gettext
- **Mobile apps**: Separate React Native apps consume the same API

### Database
- **PostgreSQL**: Primary database with extensive use of migrations
- **Redis**: Caching and session storage
- **RabbitMQ**: Message queue for background processing

### Development Environment
- Uses Django's development server for backend
- Webpack dev server for frontend asset building and hot reloading
- Virtual environment managed with uv/pip
- Node.js dependencies managed with pnpm

## Code Style and Conventions

### Python
- Follow PEP 8 with 100-character line length
- Use Ruff for linting and formatting (replaces Black/flake8)
- Type hints required (mypy enforced at 100% coverage)
- Django best practices for models, views, and migrations

### JavaScript/TypeScript
- ESLint configuration with custom rules
- Prettier for formatting
- jQuery-based architecture (legacy, but still primary frontend framework)
- TypeScript for type safety

### Testing
- Backend: Django test framework with custom test classes
- Frontend: Node.js tests with JSDOM, Puppeteer for browser tests
- Comprehensive test coverage expected for new features
- Test database migrations in both directions

## Important Files and Directories
- `manage.py`: Django management commands (filtered for end users)
- `pyproject.toml`: Python dependencies and tool configuration
- `package.json`: Node.js dependencies and npm scripts
- `tools/`: Development and testing scripts
- `scripts/`: Production deployment and maintenance scripts