![PyPI - Version](https://img.shields.io/pypi/v/omim-cli)
![PyPI - Python](https://img.shields.io/pypi/pyversions/omim-cli)
![PyPI - Status](https://img.shields.io/pypi/status/omim-cli)
![PyPI - License](https://img.shields.io/pypi/l/omim-cli)
![GitHub last commit](https://img.shields.io/github/last-commit/Liozhang/omim-cli)
![GitHub](https://img.shields.io/github/license/Liozhang/omim-cli)

---

# omim-cli — client for OMIM (Online Mendelian Inheritance in Man)

## Installation
```bash
pip install -U omim-cli
```
Requires Python ≥ 3.8.

> **First-time setup — the package ships no data.** OMIM data is copyrighted
> by Johns Hopkins University, so each user downloads their own copy with their
> own free API key (register at <https://omim.org/downloads>):
> ```bash
> omim-cli api config --set-key YOUR_KEY   # save your key once
> omim-cli download                        # fetch the 4 official text files
> omim-cli update                          # build the local SQLite database
> omim-cli stats                           # verify (~29k entries)
> ```
> Append `--with-api` to `update` to also fetch text sections, clinical
> synopsis and allelic variants via the API. Set the database location with
> `--dbfile` or the `OMIM_DB` env var. See **Basic Usage** below.

---

## Basic Usage
### main
`omim-cli -h`
```
Usage: omim-cli [OPTIONS] COMMAND [ARGS]...

  omim-cli - client for OMIM (Online Mendelian Inheritance in Man)

Options:
  -d, --dbfile TEXT  the path of database file  [default: ~/omim_data/omim.sqlite3]
  -u, --url TEXT     the base url of omim  [default: https://omim.org]
  --version          Show the version and exit.
  -?, -h, --help     Show this message and exit.

Commands:
  download  download official OMIM text files
  update    update the database from official OMIM data
  query     query something from the database
  stats     statistics of the database
  faq       explains of some faq
  api       live queries against the OMIM REST API
```

> **v2.0 — legal data sources.** The HTML scraper has been removed. Data is
> obtained exclusively from the **official OMIM API** and the **official
> text-file downloads** (`mim2gene.txt`, `mimTitles.txt`, `genemap2.txt`,
> `morbidmap.txt`). The same free OMIM API key doubles as the download token
> (register at <https://omim.org/downloads>); see **Installation** for setup.

### 1. stats
> OMIM Entry Statistics

`omim-cli stats`
```
***** updated time: 2026-07-17 *****
+--------------------------+-------+
| MIM_TYPE                 | COUNT |
+--------------------------+-------+
| gene                     | 17859 |
| phenotype                | 8645  |
| predominantly phenotypes | 1737  |
| moved/removed            | 1383  |
| TOTAL COUNT              | 29624 |
+--------------------------+-------+
```

### 2. download
> download the four official OMIM text files (`mim2gene.txt`,
> `mimTitles.txt`, `genemap2.txt`, `morbidmap.txt`) into a local directory.
> Re-running only re-downloads files whose `# Generated:` date changed.

```
omim-cli download                    # all 4 files, into the current directory
omim-cli download -o ./data          # into ./data
omim-cli download genemap2 morbidmap # only specific files
omim-cli download --force            # re-download even if up to date
```

### 3. update
> build / refresh the local SQLite database from the downloaded text files.

```
omim-cli update                      # import text files only (fast, no API calls)
omim-cli update --with-api           # also fetch text sections, clinical synopsis
                                 # and allelic variants via the API (slower)
omim-cli update --with-api --refresh # probe entry dates via API and re-fetch only
                                 # entries OMIM has updated (lightweight detection)
omim-cli update --force              # re-import everything
omim-cli update -d ./data            # use text files in ./data
omim-cli update -t gene -t phenotype # restrict to given mim types
```

> **Default mode imports only structured data** (`prefix`, `title`, `geneMap`,
> `phenotypeMap`, gene identifiers, `phenotypic_series`). The deep fields
> (`text_sections`, `clinical_synopsis`, `allelic variants`, `references`) are
> populated only with `--with-api`, because the text files do not carry them.
>
> **Incremental — no wasted work.** Re-running `omim-cli update` is a no-op when
> nothing changed: it compares the text files' `# Generated:` date and the
> parser version against the database, and skips the import entirely if current
> (use `--force` to re-import). `--with-api` only queries entries that have not
> been enriched yet (tracked via the `external_links` marker), so a second run
> on an already-enriched database skips all API calls. To catch **OMIM-side
> updates** to already-enriched entries without re-fetching everything, use
> `--refresh`: it probes each entry's `dateUpdated` in lightweight batches of 20
> (`include=dates`) and re-fetches full data only for the entries that changed.

> **Default database path.** Set the `OMIM_DB` (or `OMIM_DBFILE`) environment
> variable to change the default database location once for all commands,
> instead of passing `--dbfile` every time.

### 4. faq
> explains of some FAQ

`omim-cli faq`
```
***** Explains of MIM PREFIX *****
+--------+---------------------------------------------------------+
| PREFIX | EXPLAIN                                                 |
+--------+---------------------------------------------------------+
|   *    | Gene description                                        |
|   +    | Gene and phenotype, combined                            |
|   #    | Phenotype description, molecular basis known            |
|   %    | Phenotype description or locus, molecular basis unknown |
|        | Other, mainly phenotypes with suspected mendelian basis |
|   ^    | Moved/Removed                                           |
+--------+---------------------------------------------------------+
***** Explains of PHENOTYPE SYMBOL *****
+--------+------------------------------------------------------------------------------------------------------------------------------+
| SYMBOL | EXPLAIN                                                                                                                      |
+--------+------------------------------------------------------------------------------------------------------------------------------+
|  [ ]   | indicate "nondiseases," mainly genetic variations that lead to apparently abnormal laboratory test values                    |
|  { }   | indicate mutations that contribute to susceptibility to multifactorial disorders                                             |
|        | (e.g., diabetes, asthma) or to susceptibility to infection                                                                   |
|   ?    | before the phenotype name indicates that the relationship between the phenotype and gene is provisional.                     |
|        | More details about this relationship are provided in the comment field of the map and in the gene and phenotype OMIM entries |
|  (1)   | the disorder was positioned by mapping of the wildtype gene                                                                  |
|  (2)   | the disease phenotype itself was mapped                                                                                      |
|  (3)   | the molecular basis of the disorder is known                                                                                 |
|  (4)   | the disorder is a chromosome deletion or duplication syndrome                                                                |
+--------+------------------------------------------------------------------------------------------------------------------------------+
```

### 5. query
`omim-cli query -h`
```
Usage: omim-cli query [OPTIONS]

  query something from database

Options:
  -K, --keys               list the available keys
  -s, --search TEXT...     the search string
  -l, --limit INTEGER      limit for output
  -F, --format [json|tsv]  the format for output
  -o, --outfile TEXT       the output filename [stdout]
  -C, --color              colorful print for json
  -f, --fuzzy              fuzzy search
  --count                  count the number of results
  -h, -?, --help           Show this message and exit.
```

- show all available keys

`omim-cli query -K` 
```
+----------------------+------------------------------------------+--------------+
| Key                  | Comment                                  | Type         |
+----------------------+------------------------------------------+--------------+
| mim_number           | MIM Number                               | VARCHAR(10)  |
| prefix               | The prefix symbol                        | VARCHAR(1)   |
| title                | The title                                | VARCHAR(300) |
| references           | The references                           | TEXT         |
| geneMap              | The geneMap data (JSON)                  | TEXT         |
| phenotypeMap         | The phenotypeMap data (JSON)             | TEXT         |
| mim_type             | The mim_type                             | VARCHAR(20)  |
| entrez_gene_id       | The entrez_gene_id                       | VARCHAR(20)  |
| ensembl_gene_id      | The ensembl_gene_id                      | VARCHAR(20)  |
| hgnc_gene_symbol     | The hgnc_gene_symbol                     | VARCHAR(20)  |
| generated            | The generated time                       | DATETIME     |
| text_sections        | Full text subsections (JSON)             | TEXT         |
| clinical_synopsis    | Clinical synopsis with ontology IDs      | TEXT         |
| phenotypic_series    | Phenotypic series MIM numbers            | TEXT         |
| parser_version       | Parser version                           | VARCHAR(10)  |
| status               | Entry status (live/moved/removed)        | VARCHAR(20)  |
| moved_to             | Target MIM if moved                      | VARCHAR(20)  |
| external_links       | External DB cross-references (JSON)      | TEXT         |
| gene_record          | Full gene-map record (JSON)              | TEXT         |
| see_also             | See-also references (JSON)               | TEXT         |
| contributors         | Contributors                             | TEXT         |
| edit_history         | Edit history                             | TEXT         |
| date_created         | Entry creation date                      | DATETIME     |
| date_updated         | Entry last update date                   | DATETIME     |
+----------------------+------------------------------------------+--------------+
```

> Run `omim-cli query -K` to see the columns of your local database (the
> `omim_allelic_variants` table holds allelic variants, queried via
> `manager.get_variants(mim)`).

- search with a key

`omim-cli query -s hgnc_gene_symbol BMPR2`

<details>


```
phenotypeMap	references	prefix	mim_number	generated	ensembl_gene_id	mim_type	geneMap	title	hgnc_gene_symbol	entrez_gene_id
None	16429403, 10051328, 17425602, 18548003, 10903931, 21920918, 12571257, 3291115, 12358323, 10973254, 16429395, 11115378, 14583445, 18626305, 18321866, 11484688, 18496036, 18792970, 7644468, 12045205, 12446270, 15965979, 24446489, 11015450, 19620182	*	600799	2021-04-14	ENSG00000204217	gene	[{"Location": "2q33.1-q33.2", "Phenotype": "Pulmonary hypertension, familial primary, 1, with or without HHT", "Phenotype MIM number": "178600", "Inheritance": "AD", "Phenotype mapping key": "3"}, {"Location": "2q33.1-q33.2", "Phenotype": "Pulmonary hypertension, primary, fenfluramine or dexfenfluramine-associated", "Phenotype MIM number": "178600", "Inheritance": "AD", "Phenotype mapping key": "3"}, {"Location": "2q33.1-q33.2", "Phenotype": "Pulmonary venoocclusive disease 1", "Phenotype MIM number": "265450", "Inheritance": "AD", "Phenotype mapping key": "3"}]	BONE MORPHOGENETIC PROTEIN RECEPTOR, TYPE II; BMPR2	BMPR2	659
```

</details>


- search with a key and output as json

`omim-cli query -s hgnc_gene_symbol BMPR2 -F json -C`

<details>

```json
[
  {
    "phenotypeMap": null,
    "references": "16429403, 10051328, 17425602, 18548003, 10903931, 21920918, 12571257, 3291115, 12358323, 10973254, 16429395, 11115378, 14583445, 18626305, 18321866, 11484688, 18496036, 18792970, 7644468, 12045205, 12446270, 15965979, 24446489, 11015450, 19620182",
    "prefix": "*",
    "mim_number": "600799",
    "generated": "2021-04-14",
    "ensembl_gene_id": "ENSG00000204217",
    "mim_type": "gene",
    "geneMap": [
      {
        "Location": "2q33.1-q33.2",
        "Phenotype": "Pulmonary hypertension, familial primary, 1, with or without HHT",
        "Phenotype MIM number": "178600",
        "Inheritance": "AD",
        "Phenotype mapping key": "3"
      },
      {
        "Location": "2q33.1-q33.2",
        "Phenotype": "Pulmonary hypertension, primary, fenfluramine or dexfenfluramine-associated",
        "Phenotype MIM number": "178600",
        "Inheritance": "AD",
        "Phenotype mapping key": "3"
      },
      {
        "Location": "2q33.1-q33.2",
        "Phenotype": "Pulmonary venoocclusive disease 1",
        "Phenotype MIM number": "265450",
        "Inheritance": "AD",
        "Phenotype mapping key": "3"
      }
    ],
    "title": "BONE MORPHOGENETIC PROTEIN RECEPTOR, TYPE II; BMPR2",
    "hgnc_gene_symbol": "BMPR2",
    "entrez_gene_id": "659"
  }
]
```

</details>

- fuzzy search

`omim-cli query -s geneMap '%Pulmonary hypertension%' --fuzzy -F json -C`

<details>

```json
[
  {
    "phenotypeMap": null,
    "references": "16429403, 10051328, 17425602, 18548003, 10903931, 21920918, 12571257, 3291115, 12358323, 10973254, 16429395, 11115378, 14583445, 18626305, 18321866, 11484688, 18496036, 18792970, 7644468, 12045205, 12446270, 15965979, 24446489, 11015450, 19620182",
    "prefix": "*",
    "mim_number": "600799",
    "generated": "2021-04-14",
    "ensembl_gene_id": "ENSG00000204217",
    "mim_type": "gene",
    "geneMap": [
      {
        "Location": "2q33.1-q33.2",
        "Phenotype": "Pulmonary hypertension, familial primary, 1, with or without HHT",
        "Phenotype MIM number": "178600",
        "Inheritance": "AD",
        "Phenotype mapping key": "3"
      },
      {
        "Location": "2q33.1-q33.2",
        "Phenotype": "Pulmonary hypertension, primary, fenfluramine or dexfenfluramine-associated",
        "Phenotype MIM number": "178600",
        "Inheritance": "AD",
        "Phenotype mapping key": "3"
      },
      {
        "Location": "2q33.1-q33.2",
        "Phenotype": "Pulmonary venoocclusive disease 1",
        "Phenotype MIM number": "265450",
        "Inheritance": "AD",
        "Phenotype mapping key": "3"
      }
    ],
    "title": "BONE MORPHOGENETIC PROTEIN RECEPTOR, TYPE II; BMPR2",
    "hgnc_gene_symbol": "BMPR2",
    "entrez_gene_id": "659"
  },
  {
    "phenotypeMap": null,
    "references": "22474227, 18237401, 11498544, 9837809, 9662443, 9801158, 16973879, 10079111, 25898808, 29562231, 2541345, 1360410, 15539149, 18211975, 16051704, 1512286, 22328087, 10988071, 15353589, 16001074, 11739396, 11457855, 8552590, 7608210, 26176221, 21610094, 11358800, 21654750, 17178917, 9741627, 16890161, 9717814, 16670769, 12177436, 19487814",
    "prefix": "*",
    "mim_number": "601047",
    "generated": "2021-04-14",
    "ensembl_gene_id": "ENSG00000105974",
    "mim_type": "gene",
    "geneMap": [
      {
        "Location": "7q31.2",
        "Phenotype": "?Lipodystrophy, congenital generalized, type 3",
        "Phenotype MIM number": "612526",
        "Inheritance": "AR",
        "Phenotype mapping key": "3"
      },
      {
        "Location": "7q31.2",
        "Phenotype": "Lipodystrophy, familial partial, type 7",
        "Phenotype MIM number": "606721",
        "Inheritance": "AD",
        "Phenotype mapping key": "3"
      },
      {
        "Location": "7q31.2",
        "Phenotype": "Pulmonary hypertension, primary, 3",
        "Phenotype MIM number": "615343",
        "Inheritance": "AD",
        "Phenotype mapping key": "3"
      }
    ],
    "title": "CAVEOLIN 1; CAV1",
    "hgnc_gene_symbol": "CAV1",
    "entrez_gene_id": "857"
  },
  {
    "phenotypeMap": null,
    "references": "18250325, 9312005, 12198146, 11749039, 9721223, 23883380, 10575216, 16574908, 32499642",
    "prefix": "*",
    "mim_number": "603220",
    "generated": "2021-04-14",
    "ensembl_gene_id": "ENSG00000171303",
    "mim_type": "gene",
    "geneMap": [
      {
        "Location": "2p23.3",
        "Phenotype": "Pulmonary hypertension, primary, 4",
        "Phenotype MIM number": "615344",
        "Inheritance": "AD",
        "Phenotype mapping key": "3"
      }
    ],
    "title": "POTASSIUM CHANNEL, SUBFAMILY K, MEMBER 3; KCNK3",
    "hgnc_gene_symbol": "KCNK3",
    "entrez_gene_id": "3777"
  },
  {
    "phenotypeMap": null,
    "references": "9371779, 18548003, 21920918, 19419974, 21898662, 26122142, 10583507, 24076600, 19211612, 9205116",
    "prefix": "*",
    "mim_number": "603295",
    "generated": "2021-04-14",
    "ensembl_gene_id": "ENSG00000120693",
    "mim_type": "gene",
    "geneMap": [
      {
        "Location": "13q13.3",
        "Phenotype": "Pulmonary hypertension, primary, 2",
        "Phenotype MIM number": "615342",
        "Inheritance": "AD",
        "Phenotype mapping key": "3"
      }
    ],
    "title": "SMAD FAMILY MEMBER 9; SMAD9",
    "hgnc_gene_symbol": "SMAD9",
    "entrez_gene_id": "4093"
  },
  {
    "phenotypeMap": null,
    "references": "6208196, 11474210, 18063578, 2991113, 9711878, 12655559, 21120950, 1840546, 9107685, 8486760, 7590739, 25410056, 3545062, 29801986, 28538732, 19793055, 17310273, 20154341, 16708072, 30842655, 206435, 2991241, 11407344, 6249820, 15465784, 8382576, 21767969, 7587391, 14718356, 12853138, 4944634",
    "prefix": "*",
    "mim_number": "608307",
    "generated": "2021-04-14",
    "ensembl_gene_id": "ENSG00000021826",
    "mim_type": "gene",
    "geneMap": [
      {
        "Location": "2q34",
        "Phenotype": "{Pulmonary hypertension, neonatal, susceptibility to}",
        "Phenotype MIM number": "615371",
        "Inheritance": "",
        "Phenotype mapping key": "3"
      },
      {
        "Location": "2q34",
        "Phenotype": "Carbamoylphosphate synthetase I deficiency",
        "Phenotype MIM number": "237300",
        "Inheritance": "AR",
        "Phenotype mapping key": "3"
      }
    ],
    "title": "CARBAMOYL PHOSPHATE SYNTHETASE I; CPS1",
    "hgnc_gene_symbol": "CPS1",
    "entrez_gene_id": "1373"
  },
  {
    "phenotypeMap": null,
    "references": "21255763, 15779907, 16163389, 24034276",
    "prefix": "*",
    "mim_number": "612804",
    "generated": "2021-04-14",
    "ensembl_gene_id": "ENSG00000104835",
    "mim_type": "gene",
    "geneMap": [
      {
        "Location": "19q13.2",
        "Phenotype": "Hyperuricemia, pulmonary hypertension, renal failure, and alkalosis",
        "Phenotype MIM number": "613845",
        "Inheritance": "AR",
        "Phenotype mapping key": "3"
      }
    ],
    "title": "SERYL-tRNA SYNTHETASE 2; SARS2",
    "hgnc_gene_symbol": "SARS2",
    "entrez_gene_id": "54938"
  },
  {
    "phenotypeMap": null,
    "references": "19165231",
    "prefix": "%",
    "mim_number": "612862",
    "generated": "2021-04-15",
    "ensembl_gene_id": "",
    "mim_type": "phenotype",
    "geneMap": [
      {
        "Location": "6p21.3",
        "Phenotype": "{Pulmonary hypertension, chronic thromboembolic, without deep vein thrombosis, susceptibility to}",
        "Phenotype MIM number": "612862",
        "Inheritance": "",
        "Phenotype mapping key": "2"
      }
    ],
    "title": "PULMONARY HYPERTENSION, CHRONIC THROMBOEMBOLIC, WITHOUT DEEP VEIN THROMBOSIS, SUSCEPTIBILITY TO",
    "hgnc_gene_symbol": "",
    "entrez_gene_id": "100302516"
  }
]
```

</details>

---

### 6. api
> live online queries against the official OMIM REST API (does **not** touch
> the local database). Requires an API key (register at
> <https://omim.org/downloads>).

```bash
# manage your key (stored at ~/.omim_api_key; or set OMIM_API_KEY env var)
omim-cli api config --set-key YOUR_KEY
omim-cli api config --show
omim-cli api config --clear

omim-cli api status                                  # check API status
omim-cli api entry --mim 100100                      # fetch an entry
omim-cli api entry --mim 603903 --include clinicalSynopsis geneMap
omim-cli api search -q "Marfan syndrome" --limit 20  # text search
omim-cli api gene-map --mim 602421                   # gene map data (use a gene MIM)
omim-cli api clinical-synopsis --mim 219700          # clinical synopsis
omim-cli api allelic-variants --mim 602421           # allelic variants (use a gene MIM)
omim-cli api references --mim 219700                 # reference list
omim-cli api batch --file mim_list.txt -o out.json   # batch query to file
```

> Add `--raw` to any `api` subcommand for the full JSON response. The API caps
> entry requests at 20 `mimNumber`s when an `include` is set — `batch` handles
> this automatically.

---

## Use omim-cli in Python
```python
import omim_cli
from omim_cli import util
from omim_cli.db import Manager, OMIM_DATA, OMIM_ALLELIC_VARIANT

manager = Manager(dbfile=omim_cli.DEFAULT_DB)

# show columns
print(util.get_columns_table())

# show stats
generated, table = util.get_stats_table(manager)
print(generated)
print(table)

# count the database
manager.query(OMIM_DATA).count()

# query with key-value
res = manager.query(OMIM_DATA, 'prefix', '*')
res = manager.query(OMIM_DATA, 'mim_number', '600799')
res = manager.query(OMIM_DATA, 'hgnc_gene_symbol', 'BMPR2')
res = manager.query(OMIM_DATA, 'geneMap', '%Pulmonary hypertension%', fuzzy=True)  # fuzzy query

# fetch query result
item = res.first()
items = res.all()

# content of result
print(item.mim_number, item.title)
print(item.as_dict)

# --- v2.0: deep fields (populated by `omim-cli update --with-api`) ---
import json

# text sections: API section names -> text content
text_sections = json.loads(item.text_sections)
print(list(text_sections))
# e.g. ['description', 'clinicalFeatures', 'mapping', 'molecularGenetics', ...]

# clinical synopsis: flat category fields, features carry inline ontology IDs
synopsis = json.loads(item.clinical_synopsis)
print(synopsis.get('inheritance'))
# e.g. 'Autosomal recessive {SNOMEDCT:258211005} {UMLS C0441748 HP:0000007}'

# allelic variants for a gene entry (separate table)
variants = manager.get_variants('602421')
for v in variants[:3]:
    print(v.variant_id, v.gene_symbol, v.mutation, v.rsid, v.clinvar_rcvs)
```

## Query the OMIM API directly
```python
from omim_cli.core.api import APIClient
from omim_cli.core.parser_v2 import api_to_model

# key from: argument > OMIM_API_KEY env var > ~/.omim_api_key
api = APIClient()

entry = api.get_entry('602421', include='all')   # single entry
model = api_to_model(entry)                        # -> OMIM_DATA-shaped dict
print(model['allelic_variants'][0])

for entry in api.iter_entries(['100100', '219700', '602421'], include='all'):
    print(entry['mimNumber'], entry['titles']['preferredTitle'])

resp = api.search('Marfan syndrome', limit=5)      # SOLR search
```

---

## Data & license
OMIM® and its data are copyrighted by The Johns Hopkins University. Use of OMIM
data is governed by the [OMIM User Agreement](https://omim.org/help/agreement).

- This package is a **client tool only** — it does **not** bundle or redistribute
  any OMIM data. Each user must obtain their own (free) API access and download
  the data themselves with `omim-cli download`.
- The API key is a personal, non-transferable credential. Never commit it to
  version control (the key and downloaded files are gitignored).
- This project is intended for academic research, education, and personal use.
  It is not intended for commercial use.

## Responsible use — respect the OMIM API rules
This tool is built to obtain OMIM data **legally and courteously**, in full
respect of the [OMIM API terms](https://www.omim.org/help/api):

- **Official channels only.** All data comes from the official OMIM REST API and
  the official text-file downloads — the HTML scraper was removed in v2.0.
- **Authenticated, read-only access.** Requests use the `ApiKey` header (never
  the URL, to avoid leaking the key in logs) and are GET-only.
- **Honors documented limits.** Entry requests are capped at 20 `mimNumber`s when
  an `include` is set, gene-map at 100; the tool enforces/batches these for you.
- **Polite pacing.** A short delay sits between every API request; bulk
  enrichment (`omim-cli update --with-api`) is sequential (single-threaded) and
  skips entries it has already fetched, so it does not re-burn your quota.
- **Quota-aware.** If OMIM returns `429` (quota/rate limit), the tool backs off
  and retries once, then stops with a clear message instead of hammering.
- **Be mindful of your daily quota.** `omim-cli update --with-api` over the full
  database is ~1,500 API calls; run it in chunks or only for the entries you
  need (`-t gene`, specific MIMs via the Python API) if your quota is limited.
