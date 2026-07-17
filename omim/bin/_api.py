"""`omim api` - live online queries against the official OMIM REST API.

Integrated from the standalone omim_cli.py. Uses omim.core.api.APIClient and
shares the single API key (CLI arg > OMIM_API_KEY env > ~/.omim_api_key file).

Strictly follows the OMIM API contract documented in docs/OMIM_API.md:
GET-only, ApiKey header auth, include-batch cap of 20, geneMap cap of 100,
sort values always carry asc/desc.
"""
import csv
import json

import click

from omim.core.api import (APIClient, ApiError, ApiKeyError, CONFIG_FILE,
                           ENV_VAR_KEY, ENTRY_BATCH_WITH_INCLUDE)
from omim.core.parser_v2 import api_to_model


# documented entry include options
INCLUDE_OPTIONS = [
    'text', 'existFlags', 'allelicVariantList', 'clinicalSynopsis',
    'seeAlso', 'referenceList', 'geneMap', 'externalLinks',
    'contributors', 'creationDate', 'editHistory', 'dates', 'all',
]


def _client(ctx):
    """Build an APIClient from the group-level api key (or config/env)."""
    try:
        return APIClient(api_key=ctx.obj.get('api_key'))
    except ApiKeyError as exc:
        raise click.ClickException(str(exc))


def _truncate(text, max_len=120):
    if text and len(str(text)) > max_len:
        return str(text)[:max_len] + '...'
    return text or ''


def _entry_summary(entry):
    mim = entry.get('mimNumber', '?')
    prefix = entry.get('prefix', '')
    status = entry.get('status', '')
    title = (entry.get('titles', {}) or {}).get('preferredTitle', 'No title')
    return f'[{prefix}{mim}] ({status}) {title}'


def _print_json(data):
    click.echo(json.dumps(data, indent=2, ensure_ascii=False))


@click.group(name='api',
             help=click.style('live queries against the OMIM REST API', fg='green'))
@click.option('-k', '--api-key', help='OMIM API key (or OMIM_API_KEY env, or config file)')
@click.pass_context
def api_cli(ctx, api_key):
    ctx.ensure_object(dict)
    ctx.obj['api_key'] = api_key


# ---------------------------------------------------------------------------
# entry
# ---------------------------------------------------------------------------
@api_cli.command(name='entry', help='fetch entry by MIM number(s)')
@click.option('--mim', multiple=True, required=True,
              help='MIM number(s): --mim 100100 --mim 100200')
@click.option('--include', multiple=True, type=click.Choice(INCLUDE_OPTIONS),
              help='data to include (text, clinicalSynopsis, geneMap, all, ...)')
@click.option('--exclude', multiple=True, help='data to exclude')
@click.option('--raw', is_flag=True, help='output raw JSON')
@click.option('-v', '--verbose', is_flag=True)
@click.pass_context
def cmd_entry(ctx, mim, include, exclude, raw, verbose):
    api = _client(ctx)
    mims = list(mim)
    if len(mims) > ENTRY_BATCH_WITH_INCLUDE and (include or exclude):
        raise click.ClickException(
            f'OMIM API limits entry requests to {ENTRY_BATCH_WITH_INCLUDE} '
            f'mimNumbers when include/exclude is set (got {len(mims)}).')
    try:
        entries = api.get_entries(mims, include=include or None)
    except (ApiError, ValueError) as exc:
        raise click.ClickException(str(exc))

    if raw:
        _print_json(entries)
        return
    if not entries:
        click.echo('No entries found.')
        return
    click.echo(f'Found {len(entries)} entr(ies):\n')
    for entry in entries:
        click.echo(_entry_summary(entry))
        gm_list = entry.get('geneMapList', [])
        for gm in gm_list:
            g = gm.get('geneMap', {})
            click.echo(f'  Gene Map: {g.get("geneSymbols","")} | '
                       f'Chr {g.get("chromosomeSymbol","")} | {g.get("cytoLocation","")}')
        pm_list = entry.get('phenotypeMapList', [])
        for pm in pm_list:
            p = pm.get('phenotypeMap', {})
            click.echo(f'  Phenotype: {p.get("phenotype","")} | '
                       f'Inheritance: {p.get("phenotypeInheritance","")}')
        ts_list = entry.get('textSectionList', [])
        if ts_list:
            click.echo(f'  Text Sections: {len(ts_list)}')
            if verbose:
                for ts in ts_list:
                    click.echo(f'    [{ts.get("textSectionName","")}] '
                               f'{_truncate(ts.get("textSectionContent",""), 200)}')
        click.echo()


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------
@api_cli.command(name='search', help='search entries by text')
@click.option('-q', '--query', required=True, help='search text (required)')
@click.option('--filter', 'filter_', help='filter expression')
@click.option('--sort', default='score desc', show_default=True,
              help='sort (direction asc/desc required)')
@click.option('--operator', type=click.Choice(['AND']), help='require all terms')
@click.option('--start', type=int, default=0, show_default=True)
@click.option('--limit', type=int, default=10, show_default=True)
@click.option('--retrieve', type=click.Choice(['geneMap', 'clinicalSynopsis']))
@click.option('--include', multiple=True, type=click.Choice(INCLUDE_OPTIONS))
@click.option('--raw', is_flag=True)
@click.pass_context
def cmd_search(ctx, query, filter_, sort, operator, start, limit, retrieve,
               include, raw):
    api = _client(ctx)
    try:
        resp = api.search(query, start=start, limit=limit, include=include or None,
                          retrieve=retrieve, filter_=filter_, sort=sort, operator=operator)
    except ApiError as exc:
        raise click.ClickException(str(exc))
    if raw:
        _print_json(resp)
        return
    entry_list = resp.get('entryList', [])
    total = resp.get('totalResults', 0)
    click.echo(f"Search: '{query}'")
    click.echo(f'Results: showing {len(entry_list)} of {total} (start={start})\n')
    for item in entry_list:
        click.echo(_entry_summary(item.get('entry', {})))
        click.echo()


# ---------------------------------------------------------------------------
# gene-map
# ---------------------------------------------------------------------------
@api_cli.command(name='gene-map', help='fetch gene map data')
@click.option('--mim', multiple=True, required=True, help='MIM number(s)')
@click.option('--start', type=int)
@click.option('--limit', type=int, help='max 100 per request')
@click.option('--raw', is_flag=True)
@click.pass_context
def cmd_gene_map(ctx, mim, start, limit, raw):
    api = _client(ctx)
    try:
        gm_list = api.get_gene_map(','.join(mim), start=start, limit=limit)
    except ApiError as exc:
        raise click.ClickException(str(exc))
    if raw:
        _print_json(gm_list)
        return
    if not gm_list:
        click.echo('No gene map entries found.')
        return
    click.echo(f'Gene Map: {len(gm_list)} entr(ies)\n')
    for item in gm_list:
        g = item.get('geneMap', {})
        click.echo(f'MIM {g.get("mimNumber","?")} | {g.get("geneSymbols","")} | '
                   f'Chr {g.get("chromosomeSymbol","")} | {g.get("cytoLocation","")}')
        if g.get('geneName'):
            click.echo(f'  Gene Name: {g["geneName"]}')
        click.echo()


# ---------------------------------------------------------------------------
# clinical-synopsis
# ---------------------------------------------------------------------------
@api_cli.command(name='clinical-synopsis', help='fetch clinical synopsis')
@click.option('--mim', multiple=True, required=True, help='MIM number(s)')
@click.option('--include', multiple=True,
              type=click.Choice(['clinicalSynopsis', 'existFlags', 'externalLinks',
                                 'contributors', 'creationDate', 'editHistory',
                                 'dates', 'all']))
@click.option('--raw', is_flag=True)
@click.pass_context
def cmd_clinical_synopsis(ctx, mim, include, raw):
    api = _client(ctx)
    cs_list = []
    for m in mim:
        try:
            cs_list.extend(api.get_clinical_synopsis(m, include=include or None))
        except ApiError as exc:
            raise click.ClickException(str(exc))
    if raw:
        _print_json(cs_list)
        return
    if not cs_list:
        click.echo('No clinical synopsis found.')
        return
    click.echo(f'Clinical Synopsis: {len(cs_list)} entr(ies)\n')
    for item in cs_list:
        cs = item.get('clinicalSynopsis', {})
        click.echo(f'MIM {cs.get("mimNumber","?")}:')
        for key, val in cs.items():
            if key == 'mimNumber' or key.endswith('Exists'):
                continue
            if isinstance(val, str) and val.strip():
                click.echo(f'  {key}: {_truncate(val, 300)}')
            elif isinstance(val, dict):
                for sk, sv in val.items():
                    if isinstance(sv, str) and sv.strip():
                        click.echo(f'  {key}.{sk}: {_truncate(sv, 200)}')
        click.echo()


# ---------------------------------------------------------------------------
# allelic-variants
# ---------------------------------------------------------------------------
@api_cli.command(name='allelic-variants', help='fetch allelic variant list')
@click.option('--mim', required=True, help='MIM number')
@click.option('--raw', is_flag=True)
@click.option('-v', '--verbose', is_flag=True)
@click.pass_context
def cmd_allelic_variants(ctx, mim, raw, verbose):
    api = _client(ctx)
    try:
        av_list = api.get_allelic_variants(mim)
    except ApiError as exc:
        raise click.ClickException(str(exc))
    if raw:
        _print_json(av_list)
        return
    if not av_list:
        click.echo('No allelic variants found.')
        return
    click.echo(f'Allelic Variants for MIM {mim}: {len(av_list)} variant(s)\n')
    for item in av_list:
        av = item.get('allelicVariant', {})
        click.echo(f'  AV#{av.get("number","?")} [{av.get("status","")}] {av.get("name","")}')
        if av.get('mutations'):
            click.echo(f'    Mutations: {av["mutations"]}')
        if av.get('dbSnps'):
            click.echo(f'    dbSNPs: {av["dbSnps"]}')
        if av.get('clinvarAccessions'):
            click.echo(f'    ClinVar: {av["clinvarAccessions"]}')
        if verbose and av.get('text'):
            click.echo(f'    Text: {_truncate(av["text"], 300)}')
        click.echo()


# ---------------------------------------------------------------------------
# references
# ---------------------------------------------------------------------------
@api_cli.command(name='references', help='fetch reference list')
@click.option('--mim', required=True, help='MIM number')
@click.option('--raw', is_flag=True)
@click.pass_context
def cmd_references(ctx, mim, raw):
    api = _client(ctx)
    try:
        ref_list = api.get_references(mim)
    except ApiError as exc:
        raise click.ClickException(str(exc))
    if raw:
        _print_json(ref_list)
        return
    if not ref_list:
        click.echo('No references found.')
        return
    click.echo(f'References for MIM {mim}: {len(ref_list)}\n')
    for item in ref_list:
        ref = item.get('reference', {})
        click.echo(f'  [{ref.get("referenceNumber","?")}] {ref.get("authors","")}')
        if ref.get('title'):
            click.echo(f'      {_truncate(ref["title"], 150)}')
        if ref.get('pubmedID'):
            click.echo(f'      PubMed: {ref["pubmedID"]}')
        click.echo()


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------
@api_cli.command(name='status', help='check API status')
@click.option('--raw', is_flag=True)
@click.pass_context
def cmd_status(ctx, raw):
    api = _client(ctx)
    try:
        data = api.status()
    except ApiError as exc:
        raise click.ClickException(str(exc))
    if raw:
        _print_json(data)
        return
    _print_json(data)


# ---------------------------------------------------------------------------
# batch (download many entries to a file)
# ---------------------------------------------------------------------------
@api_cli.command(name='batch', help='batch query many MIM numbers')
@click.option('--file', 'file_', type=click.Path(exists=True),
              help='file with MIM numbers (one per line or comma-separated)')
@click.option('--mim', multiple=True, help='MIM numbers (comma-separated allowed)')
@click.option('--include', multiple=True, type=click.Choice(INCLUDE_OPTIONS))
@click.option('-o', '--output', help='output file (.json/.csv/.tsv)')
@click.option('-v', '--verbose', is_flag=True)
@click.pass_context
def cmd_batch(ctx, file_, mim, include, output, verbose):
    import time
    api = _client(ctx)

    mim_list = []
    if file_:
        with open(file_) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                first = line.split()[0] if line.split() else ''
                for p in first.split(','):
                    p = p.strip()
                    if p.isdigit():
                        mim_list.append(p)
    elif mim:
        for m in mim:
            for p in m.split(','):
                p = p.strip()
                if p.isdigit():
                    mim_list.append(p)
    else:
        raise click.ClickException('provide --file or --mim')
    mim_list = list(dict.fromkeys(mim_list))
    if not mim_list:
        raise click.ClickException('no valid MIM numbers found')
    click.echo(f'Batch query: {len(mim_list)} unique MIM number(s)\n')

    batch_size = ENTRY_BATCH_WITH_INCLUDE if include else 100
    all_entries = []
    for i in range(0, len(mim_list), batch_size):
        batch = mim_list[i:i + batch_size]
        if i > 0 and include:
            time.sleep(0.5)
        try:
            entries = api.get_entries(batch, include=include or None)
        except (ApiError, ValueError) as exc:
            click.echo(f'  batch {i // batch_size + 1} failed: {exc}', err=True)
            continue
        all_entries.extend(entries)
        if verbose:
            click.echo(f'  batch {i // batch_size + 1}: +{len(entries)}')

    if output:
        rows = [{
            'mimNumber': e.get('mimNumber'),
            'prefix': e.get('prefix'),
            'status': e.get('status'),
            'preferredTitle': (e.get('titles', {}) or {}).get('preferredTitle', ''),
        } for e in all_entries]
        _write_output(output, rows)
    else:
        for e in all_entries:
            click.echo(_entry_summary(e))
        click.echo(f'\nTotal: {len(all_entries)} entries')


def _write_output(path, rows):
    import os
    ext = os.path.splitext(path)[1].lower()
    if ext == '.json':
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(rows, f, indent=2, ensure_ascii=False)
    else:
        sep = '\t' if ext == '.tsv' else ','
        with open(path, 'w', newline='', encoding='utf-8') as f:
            if rows:
                w = csv.DictWriter(f, fieldnames=rows[0].keys(), delimiter=sep)
                w.writeheader()
                w.writerows(rows)
    click.echo(f'Results saved to {path} ({len(rows)} entries)')


# ---------------------------------------------------------------------------
# config (API key management)
# ---------------------------------------------------------------------------
@api_cli.command(name='config', help='manage the OMIM API key')
@click.option('--set-key', metavar='KEY', help='save API key to config file')
@click.option('--show', is_flag=True, help='show current key (masked)')
@click.option('--clear', is_flag=True, help='remove saved key')
def cmd_config(set_key, show, clear):
    if set_key:
        CONFIG_FILE.write_text(set_key.strip())
        try:
            CONFIG_FILE.chmod(0o600)
        except OSError:
            pass  # chmod may not work on Windows
        click.secho(f'API key saved to {CONFIG_FILE}', fg='green')
    elif show:
        import os
        key = os.environ.get(ENV_VAR_KEY) or (
            CONFIG_FILE.read_text().strip() if CONFIG_FILE.exists() else '')
        if key:
            masked = key[:6] + '****' + key[-4:] if len(key) > 10 else '****'
            src = ('Environment' if os.environ.get(ENV_VAR_KEY)
                   else 'Config file')
            click.echo(f'Current API key: {masked}')
            click.echo(f'  Source: {src}')
            click.echo(f'  Config file: {CONFIG_FILE}')
        else:
            click.echo('No API key configured.')
    elif clear:
        if CONFIG_FILE.exists():
            CONFIG_FILE.unlink()
            click.secho(f'API key removed from {CONFIG_FILE}', fg='green')
        else:
            click.echo('No saved API key found.')
    else:
        click.echo(
            'Config commands:\n'
            '  --set-key KEY   Save API key to config file\n'
            '  --show          Display current API key (masked)\n'
            '  --clear         Remove saved API key\n')


if __name__ == '__main__':
    api_cli()
