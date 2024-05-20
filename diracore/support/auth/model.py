from diracore.database.model import Model
from tortoise import fields
from tortoise.queryset import QuerySet
from tortoise.expressions import Q

from datetime import datetime

class User(Model):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=20, unique=True)
    password = fields.CharField(max_length=120, unique=True)

    tokens = fields.ReverseRelation['PersonalAccessToken']

    class QuerySet(QuerySet):
        def where_actual_token(self, token: str):
            return self.filter(
                Q(personal_access_tokens__credentials=token) &
                (Q(personal_access_tokens__expires_at__gt=datetime.now()) | Q(personal_access_tokens__expires_at__isnull=True))
            )

class PersonalAccessToken(Model):
    id=fields.IntField(pk=True)
    user=fields.ForeignKeyField('models.User')
    name=fields.CharField(max_length=256)

    credentials=fields.CharField(max_length=256)
    type=fields.CharField(max_length=256)
    abilities=fields.TextField(null=True)

    last_used_at=fields.DatetimeField(null=True)
    expires_at=fields.DatetimeField(null=True)

    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        pass

    class QuerySet(QuerySet):
        def active(self):
            return self.filter(PersonalAccessToken.q_active())

    @classmethod
    def q_active(cls):
        current_time = datetime.now()
        return Q(expires_at__isnull=True) | Q(expires_at__gt=current_time)