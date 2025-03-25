from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

def upgrade():
    # Проверяем существование колонки
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('users')]
    
    if 'is_admin' not in columns:
        # Добавляем колонку is_admin
        op.add_column('users', sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='0'))
        
        # Устанавливаем is_admin=True для администраторов
        admin_ids = [1396514552]  # Список ID администраторов
        for admin_id in admin_ids:
            op.execute(text(f"UPDATE users SET is_admin = 1 WHERE telegram_id = {admin_id}"))

def downgrade():
    # Удаляем колонку is_admin
    op.drop_column('users', 'is_admin') 