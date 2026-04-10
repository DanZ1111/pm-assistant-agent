from sqlalchemy.orm import Query
from models import Entity, User


def apply_entity_visibility_filter(query: Query, user: User) -> Query:
    """
    Owners see all entities.
    Editors and viewers see only workspace-visible entities.

    This is the sole enforcement point for entity visibility.
    Every entity query must pass through this function.

    Future M3 extension: also check entity_access table for per-user grants
    on restricted entities before returning the filtered query.
    """
    if user.role == "owner":
        return query
    return query.filter(Entity.visibility == "workspace")
