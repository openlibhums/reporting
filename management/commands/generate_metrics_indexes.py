
from django.db import connection
from django.db.utils import OperationalError, ProgrammingError
from django.core.management.base import BaseCommand

from utils.logger import get_logger

logger = get_logger(__name__)


class Command(BaseCommand):
    """ A management that generates metrics indexes for faster reporting"""

    help = "Generates database indexes on metrics for faster reporting"

    METRICS_INDEXES = {
        # We use GIN over GiST indexes as the former are more performant during
        # Lookups at the expense of lower build/update performance
        # https://www.postgresql.org/docs/current/textsearch-indexes.html
        "postgresql": [
            """
            CREATE INDEX IF NOT EXISTS articleaccess_accessed_idx
            ON public.metrics_articleaccess USING btree
            (accessed ASC NULLS LAST);
            """,
            """
            CREATE INDEX IF NOT EXISTS articleaccess_accessed_article_idx
            ON public.metrics_articleaccess USING btree
            (accessed ASC NULLS LAST, article_id ASC NULLS LAST,
            id ASC NULLS LAST,
            type COLLATE pg_catalog."default" ASC NULLS LAST
            );
            """
        ],
    }

    def handle(self, *args, **options):
        cursor = connection.cursor()
        if connection.vendor in self.METRICS_INDEXES:
            for sql in self.METRICS_INDEXES[connection.vendor]:
                try:
                    cursor.execute(sql)
                except (OperationalError, ProgrammingError) as e:
                    logger.debug(e)
                    pass # Ignore if already exists
        else:
            logger.warning(
                "Metrics indexing on %s backend not supported",
                connection.vendor,
            )
