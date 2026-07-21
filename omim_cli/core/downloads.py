"""Download and parse OMIM's official text files.

These files are the authoritative source for structured map data (geneMap,
phenotypeMap, titles, gene identifiers). They are far more complete per
request than the API and require no per-entry calls.

Files
-----
- mim2gene.txt   (public)   -> mim_type, entrez/hgnc/ensembl ids
- mimTitles.txt  (key)      -> prefix, title
- genemap2.txt   (key)      -> geneMap (gene -> phenotypes) + gene metadata
- morbidmap.txt  (key)      -> phenotypeMap (phenotype -> genes)

The same API key is used as the download token in the data.omim.org URL.
"""
import os
import re
import json
from collections import defaultdict
from pathlib import Path

import requests
from simple_loggers import SimpleLogger

from omim_cli.core.api import load_api_key
from omim_cli.core.parser_v2 import abbreviate_inheritance


DOWNLOAD_BASE = 'https://data.omim.org/downloads'
MIM2GENE_URL = 'https://omim.org/static/omim/data/mim2gene.txt'

FILES = {
    'mim2gene': {'filename': 'mim2gene.txt', 'auth': False},
    'mimTitles': {'filename': 'mimTitles.txt', 'auth': True},
    'genemap2': {'filename': 'genemap2.txt', 'auth': True},
    'morbidmap': {'filename': 'morbidmap.txt', 'auth': True},
}

# mimTitles "Prefix" word -> symbol
PREFIX_MAP = {
    'NULL': '',
    'Asterisk': '*',
    'Plus': '+',
    'Number Sign': '#',
    'Percent': '%',
    'Caret': '^',
}

# Trailing ", MIM (key)[, Inheritance]" anchor shared by genemap2 Phenotypes
# and morbidmap Phenotype columns.
_PHENO_TAIL_RE = re.compile(
    r'(?:,\s*(?P<mim>\d{6}))?\s*\((?P<key>\d)\)(?:,\s*(?P<inh>.+?))?\s*$'
)


class OmimDownloads(object):
    def __init__(self, api_key=None, outdir='.', logger=None, timeout=60):
        self.api_key = load_api_key(api_key)
        self.outdir = str(outdir)
        self.timeout = timeout
        self.logger = logger or SimpleLogger('OMIM-Downloads')
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'omim-py/2.0',
            'Accept-Encoding': 'gzip',
        })

    # ------------------------------------------------------------------
    # paths / urls
    # ------------------------------------------------------------------
    def local_path(self, name):
        return os.path.join(self.outdir, FILES[name]['filename'])

    def file_url(self, name):
        info = FILES[name]
        if info['auth']:
            return f'{DOWNLOAD_BASE}/{self.api_key}/{info["filename"]}'
        return MIM2GENE_URL

    # ------------------------------------------------------------------
    # "Generated:" date inspection
    # ------------------------------------------------------------------
    @staticmethod
    def _generated_from_text(text_iter):
        for line in text_iter:
            if isinstance(line, bytes):
                line = line.decode('utf-8', errors='ignore')
            if line.startswith('# Generated:'):
                return line.split(':', 1)[1].strip()
            if not line.startswith('#'):
                break
        return None

    def local_generated(self, name):
        path = self.local_path(name)
        if not os.path.isfile(path):
            return None
        try:
            with open(path, encoding='utf-8') as f:
                return self._generated_from_text(f)
        except (UnicodeDecodeError, OSError) as exc:
            self.logger.warning(f'cannot read local {name}: {exc}')
            return None

    def remote_generated(self, name):
        url = self.file_url(name)
        try:
            resp = self.session.get(url, stream=True, timeout=self.timeout)
            if resp.status_code != 200:
                self.logger.warning(f'cannot check remote {name}: HTTP {resp.status_code}')
                return None
            return self._generated_from_text(resp.iter_lines())
        except Exception as exc:
            self.logger.warning(f'cannot check remote {name}: {exc}')
            return None

    def check_updates(self, names=None):
        """Return list of file names that are missing or newer on the server."""
        import time
        names = names or list(FILES)
        need = []
        for i, name in enumerate(names):
            local = self.local_generated(name)
            if not local:
                need.append(name)
                continue
            if i > 0:
                time.sleep(1)  # be polite to the download host
            remote = self.remote_generated(name)
            if remote and remote != local:
                need.append(name)
        return need

    # ------------------------------------------------------------------
    # download
    # ------------------------------------------------------------------
    def download(self, names=None, force=False):
        """Download files. Returns list of actually downloaded names."""
        names = names or list(FILES)
        if force:
            need = list(names)
        else:
            need = self.check_updates(names)
        downloaded = []
        for name in need:
            url = self.file_url(name)
            path = self.local_path(name)
            self.logger.info(f'downloading {name} -> {path}')
            resp = self.session.get(url, stream=True, timeout=self.timeout)
            if resp.status_code != 200:
                self.logger.error(f'failed {name}: HTTP {resp.status_code} {resp.text[:120]}')
                continue
            with open(path, 'wb') as out:
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        out.write(chunk)
            gen = self.local_generated(name)
            self.logger.info(f'  saved {name} (Generated: {gen})')
            downloaded.append(name)
        if not downloaded:
            self.logger.info('all files up to date')
        return downloaded

    def ensure_downloaded(self, names=None):
        """Make sure files exist locally (download if missing). Returns paths."""
        names = names or list(FILES)
        missing = [n for n in names if not os.path.isfile(self.local_path(n))]
        if missing:
            self.download(missing)
        return [self.local_path(n) for n in names]

    # ------------------------------------------------------------------
    # parsers
    # ------------------------------------------------------------------
    def parse_mimTitles(self, path=None):
        """mimTitles.txt -> {mim_number: {'prefix', 'title'}}."""
        path = path or self.local_path('mimTitles')
        out = {}
        with open(path, encoding='utf-8') as f:
            for line in f:
                if not line.strip() or line.startswith('#'):
                    continue
                parts = line.rstrip('\n').split('\t')
                if len(parts) < 3:
                    continue
                prefix_word, mim, title = parts[0], parts[1], parts[2]
                out[mim] = {
                    'prefix': PREFIX_MAP.get(prefix_word, ''),
                    'title': title,
                }
        return out

    def parse_genemap2(self, path=None):
        """genemap2.txt -> {gene_mim: {gene fields + 'geneMap': [...]}}.

        Columns: Chromosome, PosStart, PosEnd, CytoLocation, ComputedCytoLocation,
        MIM Number, Gene Symbols, Gene Name, Approved Gene Symbol,
        Entrez Gene ID, Ensembl Gene ID, Comments, Phenotypes, Mouse.
        """
        path = path or self.local_path('genemap2')
        out = {}
        with open(path, encoding='utf-8') as f:
            for line in f:
                if not line.strip() or line.startswith('#'):
                    continue
                parts = line.rstrip('\n').split('\t')
                # pad short rows; warn if the line is unusually short
                # (genemap2 has 14 tab-separated columns)
                if len(parts) < 13:
                    self.logger.warning(
                        f'genemap2 line has only {len(parts)} columns (expected 14): '
                        f'{line[:80]}')
                parts += [''] * max(0, 13 - len(parts))
                (chrom, _start, _end, cyto, comp_cyto, mim, gene_symbols,
                 gene_name, approved, entrez, ensembl, _comments, phenotypes) = parts[:13]
                mouse = parts[13].strip() if len(parts) > 13 else ''
                if not mim:
                    continue
                location = comp_cyto.strip() or cyto.strip()
                gene_map = self._parse_phenotypes_column(phenotypes, location)
                hgnc = (approved.strip() or gene_symbols.split(',')[0].strip())
                # full gene-map record (store everything genemap2 provides)
                gene_record = {
                    'chromosome': chrom.strip(),
                    'genomic_position_start': _start.strip(),
                    'genomic_position_end': _end.strip(),
                    'cyto_location': cyto.strip(),
                    'computed_cyto_location': comp_cyto.strip(),
                    'gene_symbols': gene_symbols.strip(),
                    'gene_name': gene_name.strip(),
                    'approved_gene_symbol': approved.strip(),
                    'entrez_gene_id': entrez.strip(),
                    'ensembl_gene_id': ensembl.strip(),
                    'comments': _comments.strip(),
                    'mouse_gene_symbol_id': mouse,
                }
                out[mim] = {
                    'hgnc_gene_symbol': hgnc,
                    'gene_symbols': gene_symbols.strip(),
                    'gene_name': gene_name.strip(),
                    'entrez_gene_id': entrez.strip(),
                    'ensembl_gene_id': ensembl.strip(),
                    'geneMap': gene_map,
                    'gene_record': json.dumps(gene_record, ensure_ascii=False),
                }
        return out

    def parse_morbidmap(self, path=None):
        """morbidmap.txt -> {phenotype_mim: [phenotypeMap rows]}.

        Rows are keyed by the PHENOTYPE MIM (column 1's MIM) so that phenotype
        entries (#/%) get their associated genes. Gene entries get their
        phenotypes from genemap2 instead, so we do not index by gene MIM here.

        Columns: Phenotype, Gene Symbols, MIM Number (gene), Cyto Location.
        Rows whose phenotype cell has no MIM are skipped (rare; sub-features).
        """
        path = path or self.local_path('morbidmap')
        out = defaultdict(list)
        with open(path, encoding='utf-8') as f:
            for line in f:
                if not line.strip() or line.startswith('#'):
                    continue
                parts = line.rstrip('\n').split('\t')
                parts += [''] * (4 - len(parts))
                pheno_field, gene_symbols, gene_mim, location = parts[:4]
                pheno_name, pheno_mim, key = self._parse_morbidmap_phenotype(pheno_field)
                if not pheno_mim:
                    continue
                out[pheno_mim].append({
                    'Phenotype': pheno_name,
                    'Phenotype MIM number': pheno_mim,
                    'Phenotype mapping key': key,
                    'Gene/Locus And Other Related Symbols': gene_symbols.strip(),
                    'Gene MIM number': gene_mim.strip(),
                    'Location': location.strip(),
                })
        return dict(out)

    # ------------------------------------------------------------------
    # column parsing helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_phenotypes_column(text, location):
        """genemap2 Phenotypes column -> list of geneMap rows.

        Entries separated by ';'. Each entry: 'Phenotype[, mim] (key)[, Inh]'.
        """
        rows = []
        if not text or not text.strip():
            return rows
        for entry in text.split(';'):
            entry = entry.strip()
            if not entry:
                continue
            m = _PHENO_TAIL_RE.search(entry)
            if m:
                pheno = entry[:m.start()].rstrip(', ').strip()
                rows.append({
                    'Location': location,
                    'Phenotype': pheno,
                    'Phenotype MIM number': m.group('mim') or '',
                    'Inheritance': abbreviate_inheritance(m.group('inh')),
                    'Phenotype mapping key': m.group('key') or '',
                })
            else:
                rows.append({
                    'Location': location,
                    'Phenotype': entry,
                    'Phenotype MIM number': '',
                    'Inheritance': '',
                    'Phenotype mapping key': '',
                })
        return rows

    @staticmethod
    def _parse_morbidmap_phenotype(field):
        """Split a morbidmap Phenotype cell into (name, mim, mapping_key)."""
        m = _PHENO_TAIL_RE.search(field)
        if not m:
            return field.strip(), '', ''
        name = field[:m.start()].rstrip(', ').strip()
        return name, (m.group('mim') or ''), (m.group('key') or '')
