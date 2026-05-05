"""add precio_costo to productos

Revision ID: 9ca8e3d63484
Revises: a2146e371637
Create Date: 2026-05-05 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '9ca8e3d63484'
down_revision = 'a2146e371637'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('productos', sa.Column('precio_costo', sa.Integer(), nullable=False, server_default='0'))


def downgrade():
    op.drop_column('productos', 'precio_costo')
