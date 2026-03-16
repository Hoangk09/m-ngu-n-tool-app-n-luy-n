"""
Migration script for Link Bypass feature
Run this once to add the new database columns
"""
from web_app import app, db
from models import User, LinkBypass

def migrate():
    with app.app_context():
        # Create all new tables (LinkBypass)
        db.create_all()
        
        # Add new columns to User table if they don't exist
        from sqlalchemy import inspect, text
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('user')]
        
        if 'free_solves_today' not in columns:
            print("Adding 'free_solves_today' column to User table...")
            db.session.execute(text('ALTER TABLE user ADD COLUMN free_solves_today INTEGER DEFAULT 0'))
        
        if 'free_solves_date' not in columns:
            print("Adding 'free_solves_date' column to User table...")
            db.session.execute(text('ALTER TABLE user ADD COLUMN free_solves_date DATE'))
        
        db.session.commit()
        print("✅ Migration completed successfully!")

if __name__ == "__main__":
    migrate()
