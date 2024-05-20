from tortoise.models import Model as BaseModel, ModelMeta as BaseModelMeta
from tortoise import models
from tortoise.manager import Manager as BaseManager
from typing_extensions import Self
from tortoise.queryset import QuerySet

from typing import Any, Tuple, Type
from tortoise.models import MODEL

from typing_extensions import Self

from tortoise.manager import Manager
from tortoise.queryset import (
    QuerySet,
    QuerySetSingle,
)
import inflect

class Manager(BaseManager):
    def __init__(self, model=None, query_set_class=QuerySet) -> None:
        self.query_set = query_set_class
        super().__init__(model)

    def get_queryset(self) -> QuerySet:
        return self.query_set(self._model)

class ModelMeta(BaseModelMeta):
    __slots__ = ()

    def __new__(mcs, name: str, bases: Tuple[Type, ...], attrs: dict):
        new_class = super().__new__(mcs, name, bases, attrs)
        if 'QuerySet' in attrs:
            new_class._meta.manager = Manager(new_class, attrs['QuerySet'])
        if not new_class._meta.db_table:
            new_class._meta.db_table = mcs.to_snake_plural_last(new_class.__name__)
        return new_class
    
    @staticmethod
    def to_snake_plural_last(input_str):
        p = inflect.engine()
        words = []
        current_word = input_str[0].lower()

        # Проходимся по строке и собираем слова, разделяя их на основе заглавных букв
        for char in input_str[1:]:
            if char.isupper():
                words.append(current_word)  # Добавляем слово как есть, без преобразования во множественное число
                current_word = char.lower()  # Начинаем новое слово
            else:
                current_word += char
        words.append(current_word)  # Добавляем последнее слово

        # Преобразуем только последнее слово в множественное число
        words[-1] = p.plural(words[-1])

        return '_'.join(words)
    
    def __getitem__(cls: Type[MODEL], key: Any) -> QuerySetSingle[MODEL]:  # type: ignore
        return cls._getbypk(key)  # type: ignore
    
    def __getattr__(self, __name):
        if hasattr(self._meta.manager.get_queryset(), __name):
            return getattr(self._meta.manager.get_queryset(), __name)

class Model(BaseModel, metaclass=ModelMeta):
    @classmethod
    def query(cls) -> QuerySet[Self]:
        return QuerySet(cls)
    
    @classmethod
    def from_queryset(cls, queryset_class, *args, **kwargs):
        return super().from_queryset(queryset_class, *args, **kwargs)