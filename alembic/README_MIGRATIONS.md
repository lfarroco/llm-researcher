# Database Migrations

This project uses [Alembic](https://alembic.sqlalchemy.org/) for database schema migrations.

## Quick Start

All migration commands are available via the Makefile for convenience:

### Run Pending Migrations
```bash
make migrate
```

### Create a New Migration
After modifying models in `app/models.py`:
```bash
make migration msg="description of changes"
```

### Check Current Migration Status
```bash
make migrate-status
```

### View Migration History
```bash
make migrate-history
```

### Rollback Last Migration
```bash
make migrate-down
```

## How It Works

1. **Models**: Database models are defined in `app/models.py` using SQLAlchemy
2. **Auto-generation**: Alembic compares models to the database and generates migration scripts
3. **Version Control**: Migration files are stored in `alembic/versions/` and tracked in git
4. **Execution**: Migrations are run inside the Docker container against the PostgreSQL database

## Configuration

- `alembic.ini`: Main configuration file (database URL is loaded from app config)
- `alembic/env.py`: Environment setup that imports app models and database configuration
- `alembic/versions/`: Directory containing all migration scripts

## Best Practices

- Always review auto-generated migrations before committing
- Test migrations in development before deploying to production
- Never modify existing migration files after they've been committed
- Create descriptive migration messages
- Run migrations as part of deployment process

## Troubleshooting

### Migration fails with "Target database is not up to date"
Run `make migrate` to apply pending migrations

### Want to undo a migration
Run `make migrate-down` to rollback the last migration

### Database schema out of sync
Check current revision with `make migrate-status` and compare with latest migration in `alembic/versions/`
