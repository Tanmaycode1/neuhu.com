from django.db import migrations

def remove_chat_relationships(apps, schema_editor):
    """Remove any existing chat relationships before deleting users"""
    # Check if chat table exists
    try:
        with schema_editor.connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'chat_chatroom_participants'
                );
            """)
            table_exists = cursor.fetchone()[0]
            
            if table_exists:
                # Remove all chat relationships
                cursor.execute('DELETE FROM chat_chatroom_participants;')
    except Exception:
        pass

class Migration(migrations.Migration):
    dependencies = [
        ('users', '0001_initial'),  # This will be automatically set to your latest migration
    ]

    operations = [
        migrations.RunPython(remove_chat_relationships, reverse_code=migrations.RunPython.noop),
    ] 