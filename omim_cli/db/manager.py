import sqlalchemy
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.state import InstanceState

from omim_cli.db.model import Base, OMIM_ALLELIC_VARIANT

from simple_loggers import SimpleLogger


# Whitelist for migration: allowed table and column names.
# Prevents SQL injection via crafted identifiers (defense-in-depth;
# current identifiers are all hardcoded, but this adds a safety net).
_ALLOWED_TABLES = {
    'omim',
    'omim_allelic_variants',
}

_ALLOWED_COLS = {
    'omim': {
        'text_sections', 'clinical_synopsis', 'phenotypic_series',
        'parser_version', 'status', 'moved_to', 'external_links',
        'gene_record', 'see_also', 'contributors', 'edit_history',
        'date_created', 'date_updated',
    },
    'omim_allelic_variants': {
        'alternative_names', 'gnomad_snps', 'see_also',
        'status', 'moved_to',
    },
}


class Manager(object):
    """
        uri:
            - sqlite:///relative/path/to/db
            - sqlite:////absolute/path/to/db
            - sqlite:///:memory:
    """
    def __init__(self, dbfile=':memory:', echo=False, drop=False, logger=None):
        self.drop = drop
        self.dbfile = dbfile
        self.uri = f'sqlite:///{dbfile}'
        self.logger = logger or SimpleLogger('Manager')
        self.engine = sqlalchemy.create_engine(self.uri, echo=echo)
        self.engine.logger.level = self.logger.level
        self.session = self.connect()
        self._migrated = False

    def __enter__(self):
        self.create_table(drop=self.drop)
        self.migrate()
        return self

    def __exit__(self, *exc_info):
        self.session.commit()
        self.session.close()
        self.logger.debug('database closed.')

    def connect(self):
        DBSession = sessionmaker(bind=self.engine)
        return DBSession()

    def create_table(self, drop=False):
        if drop:
            Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)

    def migrate(self):
        """Add new columns to existing tables if they don't exist.

        SQLite does not support 'ADD COLUMN IF NOT EXISTS' directly, so we
        check via PRAGMA table_info and add missing columns. Handles both the
        ``omim`` and ``omim_allelic_variants`` tables across schema versions.

        Runs only once per Manager lifetime (cached via ``self._migrated``).
        """
        if self._migrated:
            return
        self._migrated = True

        schema = {
            'omim': {
                'text_sections': 'TEXT',
                'clinical_synopsis': 'TEXT',
                'phenotypic_series': 'TEXT',
                'parser_version': 'VARCHAR(10)',
                'status': 'VARCHAR(20)',
                'moved_to': 'VARCHAR(20)',
                'external_links': 'TEXT',
                'gene_record': 'TEXT',
                'see_also': 'TEXT',
                'contributors': 'TEXT',
                'edit_history': 'TEXT',
                'date_created': 'DATETIME',
                'date_updated': 'DATETIME',
            },
            'omim_allelic_variants': {
                'alternative_names': 'TEXT',
                'gnomad_snps': 'TEXT',
                'see_also': 'TEXT',
                'status': 'VARCHAR(20)',
                'moved_to': 'VARCHAR(20)',
            },
        }

        with self.engine.connect() as conn:
            for table, cols in schema.items():
                if table not in _ALLOWED_TABLES:
                    continue
                rows = conn.execute(
                    sqlalchemy.text(f"PRAGMA table_info({table})")
                ).fetchall()
                existing = {row[1] for row in rows}
                if not existing:
                    continue  # table does not exist yet; create_all handles it
                allowed = _ALLOWED_COLS.get(table, set())
                for col_name, col_type in cols.items():
                    if col_name not in allowed:
                        continue  # skip identifiers not in whitelist
                    if col_name not in existing:
                        self.logger.info(f'Migration: adding column {col_name} to {table}')
                        conn.execute(sqlalchemy.text(
                            f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"
                        ))
                        conn.commit()
        self.session.commit()

    def query(self, Meta, key=None, value=None, fuzzy=False):
        query = self.session.query(Meta)
        if key:
            if key not in Meta.__dict__:
                raise ValueError(f'unavailable key: {key}')

            if fuzzy:
                query = query.filter(Meta.__dict__[key].like(value))
            else:
                query = query.filter(Meta.__dict__[key] == value)

        return query

    def delete(self, Meta, key, value):
        res = self.query(Meta, key, value)
        if res.count():
            self.logger.debug(f'delete one item: {res.first()}')
            res.delete()
        else:
            self.logger.debug(f'key input not in database: {key}={value}')

    def insert(self, Meta, key, datas, upsert=True):
        """
            upsert: add when key not exists, update when key exists
        """
        if isinstance(datas, Base):
            datas = [datas]

        for data in datas:
            res = self.query(Meta, key, data.__dict__[key])
            if not res.first():
                self.logger.debug(f'>>> insert data: {data}')
                self.session.add(data)
            elif upsert:
                self.logger.debug(f'>>> update data: {data}')
                context = {k: v for k, v in data.__dict__.items() if not isinstance(v, InstanceState)}
                res.update(context)
        self.session.commit()  # commit immediately to avoid data loss on crash

    def insert_variants(self, mim_number, variants):
        """Bulk insert or refresh allelic variants for a MIM entry.
        Deletes existing variants for this mim_number, then inserts new ones."""
        if not variants:
            return

        # Delete existing variants for this entry
        self.session.query(OMIM_ALLELIC_VARIANT).filter(
            OMIM_ALLELIC_VARIANT.mim_number == mim_number
        ).delete()

        # Insert new variants
        for v in variants:
            v['mim_number'] = mim_number
            obj = OMIM_ALLELIC_VARIANT(**v)
            self.session.add(obj)
            self.logger.debug(f'>>> insert variant: {obj}')

        self.session.commit()  # commit immediately to avoid data loss on crash

    def get_variants(self, mim_number):
        """Query all allelic variants for a MIM entry."""
        return self.session.query(OMIM_ALLELIC_VARIANT).filter(
            OMIM_ALLELIC_VARIANT.mim_number == mim_number
        ).all()
