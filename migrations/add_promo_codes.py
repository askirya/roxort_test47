from alembic import op
import sqlalchemy as sa
from datetime import datetime

def upgrade():
    op.create_table(
        'promo_codes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('is_used', sa.Boolean(), default=False),
        sa.Column('used_by', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )

def downgrade():
    op.drop_table('promo_codes') 