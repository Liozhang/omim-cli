import prettytable

from omim_cli import MIM_TYPES
from omim_cli.db import OMIM_DATA_COLUMNS, OMIM_DATA


def get_columns_table():
    table = prettytable.PrettyTable(['Key', 'Comment', 'Type'])
    for k, v in OMIM_DATA_COLUMNS.items():
        table.add_row([k, v.comment, v.type])
    for field in table._field_names:
        table.align[field] = 'l'
    return table


def get_stats_table(manager):
    with manager:
        query = manager.query(OMIM_DATA)
        first_row = query.order_by(OMIM_DATA.generated.desc()).first()
        generated = (first_row.generated.strftime('%Y-%m-%d')
                     if first_row and first_row.generated else 'N/A')

        total = 0
        table = prettytable.PrettyTable(['MIM_TYPE', 'COUNT'])
        for mim_type in MIM_TYPES:
            res = manager.query(OMIM_DATA, 'mim_type', mim_type)
            count = res.count() if res else 0
            table.add_row([mim_type, count])
            total += count

        table.add_row(['TOTAL COUNT', total])
        table.align['MIM_TYPE'] = 'l'
        table.align['COUNT'] = 'l'

    return generated, table
