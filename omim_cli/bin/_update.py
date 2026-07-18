import os
import json
import datetime

import click

from omim_cli import MIM_TYPES, PARSER_VERSION
from omim_cli.db import OMIM_DATA
from omim_cli.core import OMIM
from omim_cli.core.downloads import OmimDownloads
from omim_cli.core.api import APIClient, ApiError, ApiKeyError, QuotaExhausted
from omim_cli.core.parser_v2 import api_to_model


__epilog__ = click.style('''

\b
examples:
    omim update                         # import text files only (default)
    omim update --with-api               # also enrich deep content via API
    omim update --force                  # re-import everything
    omim update -t gene -t phenotype     # restrict to given mim types
    omim update -d ./data --with-api     # use files in ./data
''', fg='yellow')


@click.command(name='update',
               help=click.style('update the database from official OMIM data', fg='green'),
               epilog=__epilog__)
@click.option('-k', '--api-key', help='OMIM API key (also the download token)')
@click.option('--with-api', help='enrich deep content (text/synopsis/variants) via API',
              is_flag=True)
@click.option('--refresh', help='probe entry dates via API and only re-fetch changed '
              'entries (implies --with-api; needs prior enrichment)', is_flag=True)
@click.option('--force', help='re-import / re-enrich even if up to date', is_flag=True)
@click.option('-d', '--data-dir', help='directory of text files', default='.', show_default=True)
@click.option('-t', '--mim-types', help='restrict to mim types',
              type=click.Choice(MIM_TYPES), show_choices=True, multiple=True)
@click.pass_context
def main(ctx, api_key, with_api, refresh, force, data_dir, mim_types):
    logger = ctx.obj['logger']
    manager = ctx.obj['manager']
    if refresh:
        with_api = True
    logger.debug(f'input arguments: with_api={with_api}, refresh={refresh}, '
                 f'force={force}, data_dir={data_dir}, mim_types={mim_types}')

    # ------------------------------------------------------------------
    # 1. ensure text files present + parse them
    # ------------------------------------------------------------------
    try:
        dl = OmimDownloads(api_key=api_key, outdir=data_dir, logger=logger)
    except ApiKeyError as exc:
        click.secho(str(exc), fg='red', err=True)
        exit(1)

    missing = [n for n in ('mim2gene', 'mimTitles', 'genemap2', 'morbidmap')
               if not os.path.isfile(dl.local_path(n))]
    if missing:
        click.secho(f'text file(s) missing: {missing}. Run `omim download` first.',
                    fg='red', err=True)
        exit(1)

    logger.info('parsing text files ...')
    titles = dl.parse_mimTitles()
    genemap = dl.parse_genemap2()
    morbidmap = dl.parse_morbidmap()
    mim2gene = dict(OMIM().parse_mim2gene(dl.local_path('mim2gene'), mim_types=None))

    generated = next((c['generated'] for c in mim2gene.values()), None) \
        or datetime.datetime.now()

    # ------------------------------------------------------------------
    # 2. merge into records {mim: fields}
    # ------------------------------------------------------------------
    records = {}

    for mim, c in mim2gene.items():
        records[mim] = {
            'mim_number': mim,
            'mim_type': c.get('mim_type', ''),
            'entrez_gene_id': c.get('entrez_gene_id', ''),
            'hgnc_gene_symbol': c.get('hgnc_gene_symbol', ''),
            'ensembl_gene_id': c.get('ensembl_gene_id', ''),
            'generated': generated,
        }

    for mim, t in titles.items():
        rec = records.setdefault(mim, {'mim_number': mim, 'generated': generated})
        rec['prefix'] = t['prefix']
        rec['title'] = t['title']

    for mim, g in genemap.items():
        rec = records.setdefault(mim, {'mim_number': mim, 'generated': generated})
        if g['geneMap']:
            rec['geneMap'] = json.dumps(g['geneMap'], ensure_ascii=False)
        if g.get('gene_record'):
            rec['gene_record'] = g['gene_record']
        if g['hgnc_gene_symbol']:
            rec['hgnc_gene_symbol'] = g['hgnc_gene_symbol']
        if g['entrez_gene_id']:
            rec['entrez_gene_id'] = g['entrez_gene_id']
        if g['ensembl_gene_id']:
            rec['ensembl_gene_id'] = g['ensembl_gene_id']

    for mim, rows in morbidmap.items():
        rec = records.setdefault(mim, {'mim_number': mim, 'generated': generated})
        rec['phenotypeMap'] = json.dumps(rows, ensure_ascii=False)

    # derive phenotypic_series from geneMap phenotype MIMs (text-mode fallback)
    for rec in records.values():
        gm = rec.get('geneMap')
        if gm:
            series = []
            for entry in json.loads(gm):
                pmim = (entry.get('Phenotype MIM number') or '').strip()
                if pmim and pmim not in series:
                    series.append(pmim)
            if series:
                rec['phenotypic_series'] = ','.join(series)

    # mim_types filter
    if mim_types:
        records = {m: r for m, r in records.items() if r.get('mim_type') in mim_types}

    # every record is text-imported at current version
    for rec in records.values():
        rec['parser_version'] = PARSER_VERSION

    logger.info(f'merged {len(records)} entries; writing to database ...')

    # ------------------------------------------------------------------
    # 3. bulk upsert (text data) — skipped if DB already at this data version
    # ------------------------------------------------------------------
    do_import = True
    if not force:
        with manager:
            if manager.query(OMIM_DATA).count() > 0:
                latest = manager.query(OMIM_DATA).order_by(
                    OMIM_DATA.generated.desc()).first()
                db_gen = (latest.generated.strftime('%Y-%m-%d')
                          if latest and latest.generated else None)
                file_gen = generated.strftime('%Y-%m-%d') if generated else None
                # rows still on an older parser version need a full re-import
                stale = manager.session.query(OMIM_DATA).filter(
                    OMIM_DATA.parser_version != PARSER_VERSION).count()
                if db_gen and db_gen == file_gen and stale == 0:
                    click.secho(
                        f'*** text data already up to date (Generated: {db_gen}, '
                        f'parser v{PARSER_VERSION}). Skipping import. '
                        f'Use --force to re-import.', fg='green')
                    do_import = False

    if do_import:
        with manager:
            kept = 0
            for rec in records.values():
                obj = OMIM_DATA(**{k: v for k, v in rec.items() if v is not None})
                manager.session.merge(obj)
                kept += 1
                if kept % 2000 == 0:
                    manager.session.commit()
                    click.secho(f'  ... {kept}/{len(records)} imported', fg='cyan')
            manager.session.commit()
        click.secho(f'*** imported {kept} entries from text files', fg='green')

    # ------------------------------------------------------------------
    # 4. optional API enrichment
    # ------------------------------------------------------------------
    if not with_api:
        click.secho('use --with-api to also fetch text sections, clinical synopsis '
                    'and allelic variants via the API', fg='yellow')
        return

    try:
        api = APIClient(api_key=api_key, logger=logger)
    except ApiKeyError as exc:
        click.secho(str(exc), fg='red', err=True)
        exit(1)

    BATCH = 20  # API cap per request when an include is set
    mims = list(records.keys())

    def apply_entry(entry):
        """Write all API fields for one entry onto its row. Returns mim or None."""
        mim = str(entry.get('mimNumber'))
        api_data = api_to_model(entry)
        existing = manager.query(OMIM_DATA, 'mim_number', mim).first()
        if not existing:
            return None
        for field in ('text_sections', 'clinical_synopsis', 'references',
                      'phenotypic_series', 'status', 'moved_to', 'gene_record',
                      'see_also', 'contributors', 'edit_history',
                      'date_created', 'date_updated'):
            if api_data.get(field) is not None:
                setattr(existing, field, api_data[field])
        # external_links doubles as the "enriched" marker: always set it
        setattr(existing, 'external_links', api_data.get('external_links') or '{}')
        variants = api_data.get('allelic_variants')
        if variants:
            manager.session.commit()
            manager.insert_variants(mim, variants)
        return mim

    # ------------------------------------------------------------------
    # 4a. --refresh: probe dates, re-fetch only changed entries
    # ------------------------------------------------------------------
    if refresh:
        from dateutil import parser as _dateparse

        def _norm(v):
            if not v:
                return None
            try:
                return _dateparse.parse(str(v)).strftime('%Y-%m-%d')
            except Exception:
                return None

        def _norm_from_epoch(epoch):
            import datetime as _dt
            if epoch is None:
                return None
            try:
                return _dt.datetime.fromtimestamp(int(epoch)).strftime('%Y-%m-%d')
            except Exception:
                return None

        click.secho(f'refresh: probing dates for {len(mims)} entries '
                    f'(include=dates, {BATCH}/batch) ...', fg='cyan')
        changed = []
        probed = 0
        probe_aborted = False
        with manager:
            for i in range(0, len(mims), BATCH):
                batch = mims[i:i + BATCH]
                try:
                    entries = api.get_entries(batch, include='dates')
                except QuotaExhausted as exc:
                    logger.error(f'API quota exhausted during date probe; stopping. {exc}')
                    probe_aborted = True
                    break
                except ApiError as exc:
                    logger.error(f'date probe failed ({batch[0]}..): {exc}')
                    continue
                for e in entries:
                    mim = str(e.get('mimNumber'))
                    remote = _norm(e.get('dateUpdated')) or _norm_from_epoch(e.get('epochUpdated'))
                    row = manager.query(OMIM_DATA, 'mim_number', mim).first()
                    local = (row.date_updated.strftime('%Y-%m-%d')
                             if row and row.date_updated else None)
                    if force or local is None or remote != local:
                        changed.append(mim)
                probed += len(batch)
                if probed % 1000 < BATCH:
                    click.secho(f'  ... probed {probed}/{len(mims)}, '
                                f'changed so far: {len(changed)}', fg='cyan')
        if probe_aborted:
            click.secho(f'*** refresh aborted: API quota exhausted after probing '
                        f'{probed}/{len(mims)} entries. Re-run later to resume.',
                        fg='yellow')
            return
        click.secho(f'*** refresh: {len(changed)} of {len(mims)} entries '
                    f'need updating', fg='yellow')

        if not changed:
            click.secho('*** refresh complete: everything up to date', fg='green')
            return

        click.secho(f'refresh: fetching full data for {len(changed)} changed entries ...',
                    fg='cyan')
        updated = 0
        refetch_aborted = False
        with manager:
            for i in range(0, len(changed), BATCH):
                batch = changed[i:i + BATCH]
                try:
                    entries = api.get_entries(batch, include='all')
                except QuotaExhausted as exc:
                    logger.error(f'API quota exhausted during refetch; stopping. {exc}')
                    refetch_aborted = True
                    break
                except ApiError as exc:
                    logger.error(f'refetch failed ({batch[0]}..): {exc}')
                    continue
                for entry in entries:
                    if apply_entry(entry):
                        updated += 1
                manager.session.commit()
                click.secho(f'  ... refreshed {i + len(batch)}/{len(changed)}', fg='cyan')
        if refetch_aborted:
            click.secho(f'*** refresh stopped early: {updated} of {len(changed)} '
                        f'updated before quota exhausted. Re-run later to resume.',
                        fg='yellow')
        else:
            click.secho(f'*** refresh complete: {updated} entries updated', fg='green')
        return

    # ------------------------------------------------------------------
    # 4b. plain --with-api: enrich entries not yet enriched (or all if --force)
    # ------------------------------------------------------------------
    logger.info('enriching deep content via API ...')
    enriched = 0
    skipped = 0
    aborted = False
    consecutive_err = 0
    MAX_CONSEC_ERR = 5
    with manager:
        for i in range(0, len(mims), BATCH):
            batch = mims[i:i + BATCH]
            todo = []
            for mim in batch:
                existing = manager.query(OMIM_DATA, 'mim_number', mim).first()
                if not existing:
                    continue
                # external_links marks v2.1-enriched entries; skip unless --force
                if not force and existing.external_links is not None:
                    skipped += 1
                    continue
                todo.append(mim)
            if not todo:
                continue
            try:
                entries = api.get_entries(todo, include='all')
            except QuotaExhausted as exc:
                logger.error(f'API quota exhausted; stopping enrichment. {exc}')
                aborted = True
                break
            except ApiError as exc:
                consecutive_err += 1
                logger.error(f'API batch failed ({todo[0]}..): {exc}')
                if consecutive_err >= MAX_CONSEC_ERR:
                    logger.error(f'{MAX_CONSEC_ERR} consecutive failures; stopping.')
                    aborted = True
                    break
                continue
            consecutive_err = 0
            for entry in entries:
                if apply_entry(entry):
                    enriched += 1
            manager.session.commit()
            click.secho(f'  ... enriched through {i + len(batch)}/{len(mims)} '
                        f'(api:{enriched}, skipped:{skipped})', fg='cyan')

    if aborted:
        click.secho(f'*** enrichment stopped early after {enriched} entries '
                    f'(quota/error). Fetched entries are committed; re-run '
                    f'later to resume (already-enriched ones are skipped).',
                    fg='yellow')
    else:
        click.secho(f'*** API enrichment done: {enriched} enriched, {skipped} skipped',
                    fg='green')


if __name__ == '__main__':
    main()
