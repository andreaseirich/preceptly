# Resetting the Database

## Recreate the database

If the database was deleted:

```bash
cd backend
python manage.py migrate
```

## Delete demo data (keep admin user)

To remove all demo data (students, lessons, contracts, invoices) while keeping the admin user:

```bash
cd backend
python manage.py clear_demo_data --confirm
```

This command deletes:
- ✅ All students
- ✅ All contracts
- ✅ All lessons
- ✅ All blocked times
- ✅ All invoices
- ✅ All lesson plans

It keeps:
- ✅ Admin user (is_staff=True)
- ✅ System settings

## Reload demo data

After deletion you can reload demo data:

```bash
python manage.py seed_demo_data
```
