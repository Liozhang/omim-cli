"""Convert OMIM API JSON responses into database-model-compatible dicts.

This is a faithful extractor: it pulls every field the API returns. The
caller (``omim.bin._update``) decides merge precedence between API data and
the authoritative text files (genemap2.txt / morbidmap.txt).
"""
import json
import re

from dateutil import parser as date_parser

from omim import PARSER_VERSION


# Inheritance abbreviation map (API/text files spell these out; legacy DB
# stored short codes). Tokens not found here are kept verbatim.
_INH_TOKENS = {
    'Autosomal dominant': 'AD',
    'Autosomal recessive': 'AR',
    'X-linked dominant': 'XLD',
    'X-linked recessive': 'XLR',
    'X-linked': 'XL',
    'Y-linked': 'YLD',
    'Mitochondrial': 'Mi',
    'Pseudoautosomal dominant': 'Pseudoautosomal dominant',
    'Pseudoautosomal recessive': 'Pseudoautosomal recessive',
    'Somatic mutation': 'Somatic mutation',
    'Somatic mosaicism': 'Somatic mosaicism',
    'Multifactorial': 'Multifactorial',
    'Isolated cases': 'Isolated cases',
    'Digenic dominant': 'Digenic dominant',
    'Digenic recessive': 'Digenic recessive',
}


def abbreviate_inheritance(text):
    """Compress a spelled-out inheritance string into OMIM short codes.

    Unknown tokens are left as-is so no data is lost.
    """
    if not text:
        return ''
    text = text.strip().lstrip('?')
    parts = [p.strip() for p in text.split(',')]
    out = [_INH_TOKENS.get(p, p) for p in parts if p]
    return ', '.join(out)


def _str(value):
    return '' if value is None else str(value)


def extract_references(entry):
    """referenceList[*].reference.pubmedID -> comma-separated string."""
    pmids = []
    for item in entry.get('referenceList', []):
        ref = item.get('reference', item) if isinstance(item, dict) else {}
        pmid = ref.get('pubmedID')
        if pmid:
            pmids.append(str(pmid))
    return ','.join(pmids) if pmids else None


def extract_text_sections(entry):
    """textSectionList -> {section_name: content} JSON string."""
    sections = {}
    for item in entry.get('textSectionList', []):
        ts = item.get('textSection', item) if isinstance(item, dict) else {}
        name = ts.get('textSectionName')
        content = ts.get('textSectionContent')
        if name and content:
            sections[name] = content
    return json.dumps(sections, ensure_ascii=False) if sections else None


def extract_gene_map(entry):
    """geneMapList -> list of phenotype-mapping rows in the legacy shape:

        {Location, Phenotype, Phenotype MIM number, Inheritance,
         Phenotype mapping key}
    """
    rows = []
    for item in entry.get('geneMapList', []):
        gm = item.get('geneMap', item) if isinstance(item, dict) else {}
        location = gm.get('cytoLocation', '') or ''
        for pm_item in gm.get('phenotypeMapList', []):
            pm = pm_item.get('phenotypeMap', pm_item) if isinstance(pm_item, dict) else {}
            rows.append({
                'Location': location,
                'Phenotype': pm.get('phenotype', '') or '',
                'Phenotype MIM number': _str(pm.get('phenotypeMimNumber')),
                'Inheritance': abbreviate_inheritance(pm.get('phenotypeInheritance')),
                'Phenotype mapping key': _str(pm.get('phenotypeMappingKey')),
            })
    return rows


def extract_phenotype_map(entry):
    """phenotypeMapList (entry-level) -> list of rows."""
    rows = []
    for item in entry.get('phenotypeMapList', []):
        pm = item.get('phenotypeMap', item) if isinstance(item, dict) else {}
        rows.append({
            'Phenotype': pm.get('phenotype', '') or '',
            'Phenotype MIM number': _str(pm.get('phenotypeMimNumber')),
            'Inheritance': abbreviate_inheritance(pm.get('phenotypeInheritance')),
            'Phenotype mapping key': _str(pm.get('phenotypeMappingKey')),
            'Phenotypic Series Number': _str(pm.get('phenotypicSeriesNumber')),
        })
    return rows


def extract_clinical_synopsis(entry):
    """clinicalSynopsis dict -> JSON string (fields keep inline ontology IDs)."""
    cs = entry.get('clinicalSynopsis')
    if not cs or not isinstance(cs, dict):
        return None
    # drop operational keys
    clean = {k: v for k, v in cs.items()
             if not k.endswith('Exists') and v not in (None, '')}
    return json.dumps(clean, ensure_ascii=False) if clean else None


def extract_phenotypic_series(entry):
    """Collect distinct phenotypic series numbers from phenotype maps."""
    seen = []
    for item in entry.get('phenotypeMapList', []):
        pm = item.get('phenotypeMap', item) if isinstance(item, dict) else {}
        ps = pm.get('phenotypicSeriesNumber')
        if ps:
            for num in str(ps).split(','):
                num = num.strip()
                if num and num not in seen:
                    seen.append(num)
    # also check geneMapList nested phenotypeMaps
    for item in entry.get('geneMapList', []):
        gm = item.get('geneMap', item) if isinstance(item, dict) else {}
        for pm_item in gm.get('phenotypeMapList', []):
            pm = pm_item.get('phenotypeMap', pm_item) if isinstance(pm_item, dict) else {}
            ps = pm.get('phenotypicSeriesNumber')
            if ps:
                for num in str(ps).split(','):
                    num = num.strip()
                    if num and num not in seen:
                        seen.append(num)
    return ','.join(seen) if seen else None


def extract_allelic_variants(entry):
    """allelicVariantList -> list of dicts shaped for OMIM_ALLELIC_VARIANT."""
    variants = []
    for item in entry.get('allelicVariantList', []):
        av = item.get('allelicVariant', item) if isinstance(item, dict) else {}
        number = av.get('number')
        if number is None:
            continue
        name = av.get('name', '') or ''
        mutations = av.get('mutations', '') or ''
        gene_symbol = _guess_gene_symbol(name) or _guess_gene_symbol(mutations)
        variants.append({
            'variant_id': '.' + str(number),
            'phenotype_name': name or None,
            'gene_symbol': gene_symbol,
            'mutation': mutations or None,
            'rsid': _first(av.get('dbSnps')),
            'clinvar_rcvs': av.get('clinvarAccessions') or None,
            'description': av.get('text') or None,
            'pubmed_ids': None,
            'alternative_names': av.get('alternativeNames') or None,
            'gnomad_snps': av.get('gnomadSnps') or None,
            'see_also': av.get('seeAlso') or None,
            'status': av.get('status') or None,
            'moved_to': _str(av.get('movedTo')) or None,
        })
    return variants or None


# ---------------------------------------------------------------------------
# v2.1: exhaustive top-level fields (store everything the API returns)
# ---------------------------------------------------------------------------
def _clean_dict(d):
    """Drop keys with empty values, keep the rest."""
    if not isinstance(d, dict):
        return None
    out = {k: v for k, v in d.items()
           if v not in (None, '', [], {})}
    return out or None


def extract_external_links(entry):
    """externalLinks dict -> JSON string (non-empty cross-references only)."""
    el = entry.get('externalLinks')
    return json.dumps(_clean_dict(el), ensure_ascii=False) if _clean_dict(el) else None


def extract_gene_record(entry):
    """Full gene-map record(s) from geneMapList, minus nested phenotype maps.

    Returns JSON list of gene-level metadata dicts.
    """
    records = []
    for item in entry.get('geneMapList', []):
        gm = item.get('geneMap', item) if isinstance(item, dict) else {}
        rec = {k: v for k, v in gm.items()
               if k != 'phenotypeMapList' and v not in (None, '', [], {})}
        if rec:
            records.append(rec)
    return json.dumps(records, ensure_ascii=False) if records else None


def _parse_date(value):
    if not value:
        return None
    try:
        return date_parser.parse(str(value))
    except (ValueError, TypeError, OverflowError):
        return None


def extract_dates(entry):
    """Returns (date_created, date_updated) as datetime or None."""
    dc_raw = entry.get('dateCreated')
    du_raw = entry.get('dateUpdated')
    dc = _parse_date(dc_raw) if dc_raw else _from_epoch(entry.get('epochCreated'))
    du = _parse_date(du_raw) if du_raw else _from_epoch(entry.get('epochUpdated'))
    return dc, du


def _from_epoch(epoch):
    """Unix epoch (seconds) -> datetime, or None."""
    import datetime as _dt
    if epoch is None:
        return None
    try:
        return _dt.datetime.fromtimestamp(int(epoch))
    except (ValueError, TypeError, OSError, OverflowError):
        return None


def _first(csv):
    if not csv:
        return None
    return str(csv).split(',')[0].strip() or None


_SYMBOL_RE = re.compile(r'^([A-Z][A-Z0-9]{1,9})\b')


def _guess_gene_symbol(name):
    """Best-effort gene symbol from an allelic variant name.

    OMIM names typically start with the symbol, e.g.
    'PHE508DEL' (no symbol), 'CFTR, 1-BP DEL', 'ALBUMIN DARLINGTON'.
    """
    if not name:
        return None
    # "SYMBOL, mutation" form
    m = re.match(r'^([A-Z][A-Z0-9]{1,9})\s*,', name)
    if m:
        return m.group(1)
    return None


def api_to_model(api_entry, mim2gene_context=None):
    """Convert one API ``entry`` dict into an OMIM_DATA-compatible dict.

    ``mim2gene_context`` (optional) supplies mim_type / gene ids that the API
    does not return.
    """
    entry = api_entry or {}
    ctx = mim2gene_context or {}

    gene_map = extract_gene_map(entry)
    phenotype_map = extract_phenotype_map(entry)
    date_created, date_updated = extract_dates(entry)
    see_also = entry.get('seeAlso')
    if isinstance(see_also, (list, dict)):
        see_also = json.dumps(see_also, ensure_ascii=False)
    elif see_also:  # OMIM returns a ';'-separated string
        items = [s.strip() for s in str(see_also).split(';') if s.strip()]
        see_also = json.dumps(items, ensure_ascii=False) if items else None
    else:
        see_also = None

    result = {
        'mim_number': _str(entry.get('mimNumber')),
        'prefix': entry.get('prefix') or '',
        'title': (entry.get('titles', {}) or {}).get('preferredTitle', '') or '',
        'references': extract_references(entry),
        'geneMap': json.dumps(gene_map, ensure_ascii=False) if gene_map else None,
        'phenotypeMap': json.dumps(phenotype_map, ensure_ascii=False) if phenotype_map else None,
        'mim_type': ctx.get('mim_type'),
        'entrez_gene_id': ctx.get('entrez_gene_id'),
        'ensembl_gene_id': ctx.get('ensembl_gene_id'),
        'hgnc_gene_symbol': ctx.get('hgnc_gene_symbol'),
        'text_sections': extract_text_sections(entry),
        'clinical_synopsis': extract_clinical_synopsis(entry),
        'phenotypic_series': extract_phenotypic_series(entry),
        'allelic_variants': extract_allelic_variants(entry),
        'parser_version': PARSER_VERSION,
        # v2.1: exhaustive fields
        'status': entry.get('status') or None,
        'moved_to': _str(entry.get('movedTo')) or None,
        'external_links': extract_external_links(entry),
        'gene_record': extract_gene_record(entry),
        'see_also': see_also,
        'contributors': entry.get('contributors') or None,
        'edit_history': entry.get('editHistory') or None,
        'date_created': date_created,
        'date_updated': date_updated,
    }
    return result
