# Database Migration Guide

This guide explains how your data persistence has been upgraded from JSON files to a proper database.

## What Changed

**Problem**: Your app was storing all data in `data.json` on Render's ephemeral disk, causing data loss when the service restarts.

**Solution**: All data is now stored in a PostgreSQL database (production) or SQLite (local development) for permanent persistence.

## Local Development Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Initialize Database

```bash
python init_db.py
```

This creates all necessary database tables.

### 3. (Optional) Migrate Existing Data

If you have existing data in `data.json`:

```bash
python migrate_json_to_db.py
```

### 4. Run the Application

```bash
python app.py
```

The app will use SQLite by default (`app.db` file) for local development.

## Render Deployment

### 1. Create PostgreSQL Database on Render

1. Go to your [Render Dashboard](https://dashboard.render.com/)
2. Click **"New +"** → **"PostgreSQL"**
3. Configure:
   - **Name**: `rsanju-db` (or any name)
   - **Database**: `rsanju`
   - **User**: `rsanju`
   - **Region**: Same as your web service
   - **Plan**: Free (or paid for better performance)
4. Click **"Create Database"**
5. Wait for it to provision (~minute)
6. Copy the **"Internal Database URL"** (starts with `postgresql://`)

### 2. Update Environment Variables

In your Render Web Service settings:

1. Go to **Environment** tab
2. Add/update the following:
   - `DATABASE_URL` = `<paste-internal-database-url>`
   - `FLASK_SECRET_KEY` = `<your-secret-key>` (keep existing or generate new)
   - `FIREBASE_CREDENTIALS` = `<your-firebase-json>` (keep existing)

### 3. Deploy Updated Code

```bash
git add .
git commit -m "Migrate to PostgreSQL database for persistent storage"
git push
```

Render will automatically deploy.

### 4. Initialize Database on Render

After deployment completes:

1. Go to your Web Service in Render
2. Click **"Shell"** button (top right)
3. Run:
   ```bash
   python init_db.py
   ```
4. (Optional) If you have production data to migrate:
   ```bash
   python migrate_json_to_db.py
   ```

### 5. Verify Everything Works

1. Visit your website
2. Log in with Firebase
3. Create a test invoice or product
4. **Restart your service** in Render dashboard
5. ✅ **Verify data is still there after restart**

## Database Format

All your data is now in these database tables:

- **users** - Firebase user accounts
- **store_settings** - Store configuration and logo (per user)
- **products** - Inventory items
- **invoices** - Sales invoices
- **invoice_items** - Line items in each invoice
- **expenses** - Business expenses
- **stock_transactions** - Inventory movement history
- **suppliers** - Supplier information

## What About data.json?

- The `data.json` file is **no longer used**
- It's safe to delete after successful migration
- Keep a backup copy if you want

## Troubleshooting

### "No module named 'psycopg2'"

Run: `pip install -r requirements.txt`

### "relation does not exist"

Run: `python init_db.py` to create database tables

### Database connection fails on Render

- Verify `DATABASE_URL` environment variable is set correctly
- Use the **Internal Database URL** (not External)
- Ensure database and web service are in the same region

### Data didn't migrate

- Check that `data.json` exists in project root
- Run `python migrate_json_to_db.py` manually
- Check for error messages in output

## Benefits

✅ **Data persists** through service restarts  
✅ **Faster queries** with proper database indexes  
✅ **Multi-user ready** with proper isolation  
✅ **Scalable** for growing business data  
✅ **Backup ready** via database snapshots  

## Need Help?

Check the application logs for error messages:
- Locally: Terminal output when running `python app.py`
- Render: **Logs** tab in your web service
