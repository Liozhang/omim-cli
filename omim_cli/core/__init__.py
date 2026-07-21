"""OMIM base helpers.

Only ``parse_mim2gene`` remains here (parses the local ``mim2gene.txt`` file).
Downloading is handled by :mod:`omim_cli.core.downloads`; the legacy HTML
scraper and its ``webrequests`` dependency were removed in v2.0.
"""
import os

from dateutil.parser import parse as date_parse

from simple_loggers import SimpleLogger


class OMIM(object):
    def __init__(self, omim_url='https://omim.org', logger=None):
        self.omim_url = omim_url
        self.logger = logger or SimpleLogger('OMIM')

    def parse_mim2gene(self, mim2gene, mim_types=('gene', 'gene/phenotype')):
        """Yield (mim_number, context) for each row of a local mim2gene.txt.

        ``mim2gene`` must be a path to an already-downloaded file
        (use ``omim-cli download`` to fetch it).
        """
        self.logger.debug(f'parsing mim2gene from file: {mim2gene} ...')
        with open(mim2gene, encoding='utf-8') as f:
            text = f.read().strip()

        fields = 'mim_number mim_type entrez_gene_id hgnc_gene_symbol ensembl_gene_id'.split()
        generated = None
        for line in text.split('\n'):
            if line.startswith('# Generated:'):
                generated = line.split(': ')[-1]
                continue
            elif line.startswith('#') or not line.strip():
                continue
            linelist = line.split('\t')
            context = dict(zip(fields, linelist))

            if mim_types and context.get('mim_type') not in mim_types:
                continue

            context['generated'] = date_parse(generated) if generated else None
            yield context['mim_number'], context


if __name__ == '__main__':
    contexts = OMIM().parse_mim2gene('mim2gene.txt', mim_types=None)
    for context in contexts:
        print(context)
