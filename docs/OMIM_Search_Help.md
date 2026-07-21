# OMIM 搜索语法与字段文档

> 本文档基于 [https://www.omim.org/help/search/method](https://www.omim.org/help/search/method)（OMIM Search Help）整理。
> OMIM 的搜索（网页搜索框与 API 的 `search` handler）均基于 **Apache SOLR / extended dismax parser**，语法统一。
> 配合 [`docs/OMIM_API.md`](./OMIM_API.md) 的 `entry/search`、`clinicalSynopsis/search`、`geneMap/search` 接口使用。

---

## 目录

- [1. 搜索语法](#1-搜索语法)
  - [1.1 基础搜索](#11-基础搜索)
  - [1.2 +/- 操作符](#12--操作符)
  - [1.3 短语搜索](#13-短语搜索)
  - [1.4 通配符搜索](#14-通配符搜索)
  - [1.5 字段搜索](#15-字段搜索)
  - [1.6 布尔操作符](#16-布尔操作符)
  - [1.7 搜索分组](#17-搜索分组)
  - [1.8 邻近搜索](#18-邻近搜索)
  - [1.9 词重加权](#19-词重加权)
  - [1.10 日期搜索](#110-日期搜索)
  - [1.11 细胞遗传学位置 / 基因组坐标搜索](#111-细胞遗传学位置--基因组坐标搜索)
- [2. OMIM 搜索字段](#2-omim-搜索字段)
  - [2.1 概览](#21-概览)
  - [2.2 示例搜索解读](#22-示例搜索解读)
  - [2.3 Entry 搜索字段表](#23-entry-搜索字段表)
  - [2.4 Clinical Synopsis 搜索字段表](#24-clinical-synopsis-搜索字段表)
  - [2.5 Gene Map 搜索字段表](#25-gene-map-搜索字段表)
- [3. 遗传方式代码表（phenotype_inheritance）](#3-遗传方式代码表phenotype_inheritance)
- [4. 与 API 结合使用](#4-与-api-结合使用)

---

## 1. 搜索语法

### 1.1 基础搜索

直接在搜索框输入词，搜索引擎会以**任意顺序**匹配，包含全部词的条目排名高于只含部分词的：

```
duchenne muscular dystrophy
```

搜索**大小写不敏感**：`duchenne` / `Duchenne` / `DUCHENNE` 等价。

### 1.2 +/- 操作符

`+` 前缀：**必须出现**该词：

```
+duchenne +muscular dystrophy
```
返回结果必含 `duchenne` 和 `muscular`，`dystrophy` 可有可无。

`-` 前缀：**排除**含该词的条目：

```
+muscular +dystrophy -duchenne
```

用括号可要求/排除"任一"词：

```
+(duchenne muscular dystrophy)    # 至少含其一
-(duchenne muscular dystrophy)    # 三者都不含
```

对短语用 `+` 要求整串出现：

```
+"duchenne muscular dystrophy"
```

### 1.3 短语搜索

两端加引号做精确短语匹配：

```
"duchenne muscular dystrophy"
```

`~` + 数字 控制词间容差（数字 = 短语内允许的中间词数）：

```
"duchenne dystrophy"~1
```
同时命中 `"duchenne dystrophy"` 和 `"duchenne muscular dystrophy"`。

与 `-` 组合排除短语：

```
"muscular dystrophy" -"duchenne gene"
```

### 1.4 通配符搜索

| 通配符 | 含义 | 示例 |
|--------|------|------|
| `?` | 单字符 | `dystrophi?` → `dystrophia`/`dystrophin`/`dystrophic`，但不含 `dystrophins` |
| `*` | 多字符 | `dystroph*` → `dystrophia`/`dystrophin`/`dystrophic`/`dystrophy` |

- `dystroph??` → 不含 `dystrophy`（需恰好 2 个替换字符）
- 通配符可放词中间：`dystro*ia`、`dystro??i?`
- **支持前导通配符**：`*cortisolism`（同时覆盖 hyper/hypo）、`hy*cortisolism`
- 拼写变体：`*glutar*`（覆盖 3-methylglutaric acid 等不同写法）

### 1.5 字段搜索

`字段名:词`（**字段名、冒号、词之间不能有空格**）：

```
title:duchenne
```

同字段多词：

```
title:duchenne title:muscular title:dystrophy
title:(duchenne muscular dystrophy)         # 分组写法更优雅
```

结合操作符：

```
title:(+duchenne +muscular +dystrophy)       # 字段内要求全部词
+title:(duchenne muscular dystrophy)         # 要求含其中任一词
title:(-duchenne -muscular -dystrophy)       # 字段内排除全部
-title:(duchenne muscular dystrophy)         # 排除含其中任一词
```

字段内短语（用引号替代括号，紧贴冒号）：

```
title:"duchenne muscular dystrophy"
+title:"duchenne muscular dystrophy"
```

### 1.6 布尔操作符

支持 `AND` / `OR` / `NOT`（**必须大写**）：

```
duchenne AND muscular AND dystrophy          # ≡ +duchenne +muscular +dystrophy
muscular AND dystrophy NOT duchenne          # ≡ +muscular +dystrophy -duchenne
```

> 💡 官方**推荐用 `+`/`-` 而非布尔操作符**，歧义更小、控制更精细。布尔操作符务必大写。

### 1.7 搜索分组

含布尔操作符时建议用括号明确优先级：

```
muscular AND dystrophy OR duchenne AND gene          # 有歧义
(muscular AND dystrophy) OR (duchenne AND gene)      # 清晰
((muscular AND dystrophy) OR (duchenne AND gene)) NOT (becker OR Emery-Dreifuss)
```

### 1.8 邻近搜索

`~` + 数字 限制两词的最大词距（**与方向无关**）：

```
"muscular dystrophy"~10
```
`muscular` 与 `dystrophy` 间隔不超过 10 个词，`muscular … dystrophy` 与 `dystrophy … muscular` 等价。

### 1.9 词重加权

`^` + 数字 调整词权重（默认权重 1）：

```
muscular dystrophy^10
```
`dystrophy` 权重提升 10 倍。

### 1.10 日期搜索

格式 `字段:日期` 或 `字段:日期范围`（`-` 分隔，`*` 代表开放端）：

| 搜索 | 含义 |
|------|------|
| `date_updated:2014/7/1` | 2014-07-01 当天更新 |
| `date_updated:2014/7` | 2014 年 7 月更新 |
| `date_updated:2014` | 2014 年更新 |
| `date_updated:2014/7/1-*` | 2014-07-01 至今 |
| `date_updated:*-2014/7/1` | 起始至 2014-07-01 |
| `date_updated:2014/7/1-2014/10/1` | 2014-07-01 至 2014-10-01 |
| `date_updated:2014-2015` | 2014 至 2015 |

相对时间关键字：

| 搜索 | 含义 |
|------|------|
| `date_updated:yesterday` | 昨天 |
| `date_updated:lastweek` | 最近一周 |
| `date_updated:lastmonth` | 最近一月 |
| `date_updated:lastyear` | 最近一年 |

### 1.11 细胞遗传学位置 / 基因组坐标搜索

gene map 索引支持 cytoband 与基因组坐标搜索：

| 搜索 | 含义 |
|------|------|
| `1p36` | 从该带（pter 端）起始的条目 |
| `1:124,300,000` | 从该位置起始的条目 |
| `1p36-p32` | 起点/终点/跨越该区域的条目 |
| `1p32-p32` | 起点/终点/跨越该带的条目 |
| `1:12,000,000-48,000,000` | 起点/终点/跨越该区域的条目 |
| `1:12,000,000-12,000,000` | 起点/终点/跨越该位置的条目 |
| `1` 或 `chr1` | 该染色体上的条目 |

---

## 2. OMIM 搜索字段

### 2.1 概览

- **未指定字段的搜索（text 搜索）**：检索 entry 的**除 external data 外的所有字段**。
- **meta 字段**：一个字段聚合多个子字段。如 `title` 同时检索 preferred/alternative/included 三类标题。
- **受限词表字段**：值域固定，如 `status`（`live`/`moved`/`removed`）、`phenotype_mapping_key`（1/2/3/4）、`phenotype_inheritance`（见 [第 3 节](#3-遗传方式代码表phenotype_inheritance)）。
- **布尔字段**：值为 `true`/`false`，如 `av_exists`、`genemap_exists`、各种 `*_exists` 标志位。
- **external data 不在 text 搜索范围内**：搜索 HGNC 符号等外部 ID 必须显式指定字段，如 `approved_gene_symbol:MZT1`。

示例：

```
status:live            # 仅 live 条目
av_exists:true         # 仅含等位变异的条目
av_exists:false        # 仅不含等位变异的条目
title:(duchenne muscular dystrophy)             # 检索 preferred+alternative+included 标题
ti_preferred:(duchenne muscular dystrophy)      # 仅检索 preferred 标题
```

### 2.2 示例搜索解读

| 输入 | 解读为 |
|------|--------|
| `blindness hypertelorism` | `blindness OR hypertelorism` |
| `+blindness +hypertelorism` | `blindness AND hypertelorism` |
| `+blindness -hypertelorism` | `blindness NOT hypertelorism` |
| `"short stature"` | 短语搜索 |

外部 ID 示例：

```
ref_pubmed_id:3294410          # 按 PubMed ID 搜参考文献
approved_gene_symbol:DMD       # 按 HGNC 批准基因符号
gene_id:1756                   # 按 NCBI Gene ID
```

按 prefix 限定（OMIM 前缀）：

```
duchenne AND prefix:*        # 基因
duchenne AND prefix:+        # 基因+表型
duchenne AND prefix:#        # 表型（分子机制已知）
duchenne AND prefix:%        # 表型（分子机制未知）
duchenne AND prefix:none     # 其他
```

### 2.3 Entry 搜索字段表

> **Meta** 列：`text` = 该字段纳入无字段搜索；`tx` = text section 元字段组；`av` = allelic variant 组；`cs` = clinical synopsis 组；`ref` = reference 组。
> **Comments** 列：`boolean` = 布尔值；`date` = 日期；`text` = 文本；`key field` = 关键字段。

#### 核心字段

| 字段名 | 描述 | Meta | 类型/备注 |
|--------|------|------|-----------|
| `text` | 默认 text 元字段 | text meta | 默认搜索字段 |
| `number` | mim number | text | key field |
| `prefix` | prefix | text | |
| `title` | 标题元字段（preferred+alternative+included） | title meta | |
| `ti_preferred` | preferred 标题 | title, text | |
| `ti_alternative` | alternative 标题 | title, text | |
| `ti_included` | included 标题 | title, text | |
| `gene_symbol` | 基因符号 | | |
| `gene_symbol_exists` | 是否有基因符号 | | boolean |
| `status` | 状态 | | live/moved/removed |
| `moved_to` | 移动目标 mim number | | |

#### Text Section 字段（`tx_*`）

| 字段名 | 描述 | 存在性标志位 |
|--------|------|--------------|
| `tx` | text section 元字段 | `tx_text_exists` |
| `tx_text` | text section | |
| `tx_animal_model` | animal model | `tx_animal_model_exists` |
| `tx_biochemical_features` | biochemical features | `tx_biochemical_features_exists` |
| `tx_clinical_features` | clinical features | `tx_clinical_features_exists` |
| `tx_clinical_management` | clinical management | `tx_clinical_management_exists` |
| `tx_cloning` | cloning | `tx_cloning_exists` |
| `tx_cytogenetics` | cytogenetics | `tx_cytogenetics_exists` |
| `tx_description` | description | `tx_description_exists` |
| `tx_diagnosis` | diagnosis | `tx_diagnosis_exists` |
| `tx_evolution` | evolution | `tx_evolution_exists` |
| `tx_gene_family` | gene family | `tx_gene_family_exists` |
| `tx_gene_function` | gene function | `tx_gene_function_exists` |
| `tx_gene_structure` | gene structure | `tx_gene_structure_exists` |
| `tx_gene_therapy` | gene therapy | `tx_gene_therapy_exists` |
| `tx_genetic_variability` | genetic variability | `tx_genetic_variability_exists` |
| `tx_genotype` | genotype | `tx_genotype_exists` |
| `tx_genotype_phenotype_correlations` | genotype phenotype correlations | `tx_genotype_phenotype_correlations_exists` |
| `tx_heterogeneity` | heterogeneity | `tx_heterogeneity_exists` |
| `tx_history` | history | `tx_history_exists` |
| `tx_inheritance` | inheritance | `tx_inheritance_exists` |
| `tx_mapping` | mapping | `tx_mapping_exists` |
| `tx_molecular_genetics` | molecular genetics | `tx_molecular_genetics_exists` |
| `tx_nomenclature` | nomenclature | `tx_nomenclatures_exists` |
| `tx_other_features` | other features | `tx_other_features_exists` |
| `tx_pathogenesis` | pathogenesis | `tx_pathogenesis_exists` |
| `tx_phenotype` | phenotype | `tx_phenotype_exists` |
| `tx_population_genetics` | population genetics | `tx_population_genetics_exists` |

#### Allelic Variant 字段（`av_*`）

| 字段名 | 描述 | Meta |
|--------|------|------|
| `av` | allelic variant 元字段 | av meta |
| `av_exists` | 是否含等位变异 | boolean |
| `av_number` | 编号，格式 `####` | av, text |
| `av_name` | 名称 | av, text |
| `av_alternative_names` | 别名 | av, text |
| `av_mutations` | 突变 | av, text |
| `av_text` | 文本 | av, text |
| `av_db_snp` | dbSNP | av, text |
| `av_clinvar_accession` | ClinVar accession | |
| `av_gnomad_snp` | gnomAD SNP | av, text / boolean |

#### Clinical Synopsis 字段（`cs_*`）

| 字段名 | 描述 |
|--------|------|
| `cs` | clinical synopsis 元字段 |
| `cs_exists` | 是否含临床概要（boolean） |
| `cs_*` | 以 `cs_` 开头的各器官系统字段（见 [2.4](#24-clinical-synopsis-搜索字段表)） |
| `cs_date_created` / `cs_date_updated` | 临床概要创建/更新日期 |

#### Reference 字段（`ref_*`）

| 字段名 | 描述 | Meta |
|--------|------|------|
| `ref` | reference 元字段 | ref meta |
| `ref_author` | 作者 | ref, text |
| `ref_title` | 标题 | ref, text |
| `ref_source` | 来源 | ref, text |
| `ref_pubmed_id` | PubMed ID | ref, text |
| `ref_article_url` | 文章 URL | ref, text |
| `ref_doi` | DOI | ref, text |

#### Gene Map / Phenotype 相关

| 字段名 | 描述 | 备注 |
|--------|------|------|
| `genemap_exists` | 是否在 gene map（基因或表型）中 | boolean |
| `phenotype_exists` | 是否作为表型/带表型的基因出现 | boolean |
| `chromosome` | 染色体 | 1-22, X, Y, M, U |
| `chromosome_number` | 染色体号 | 1-22, 23, 24, 25, 0 |
| `chromosome_group` | 染色体组 | A-Autosomal, S-XY, M-Mitochondria, U-Unset |
| `molecular_series_number` | 分子系列号 | text |
| `molecular_series_exists` | 是否在分子系列中 | boolean |
| `phenotypic_series_number` | 表型系列号 | text |
| `phenotypic_series_exists` | 是否在表型系列中 | boolean |
| `phenotype_mapping_key` | 表型映射键 | 1/2/3/4 |
| `imprinting_region_exists` | 是否在印记区 | boolean |
| `see_also` | see also | text |
| `contributors` | contributors | text |
| `creator` | creator | text |
| `date_created` / `date_updated` | 创建/更新日期 | date |

#### External Data（不纳入 text 搜索，须显式指定字段）

| 字段名 | 描述 |
|--------|------|
| `gene_id` | NCBI Gene ID |
| `ncbi_reference_sequence` | NCBI reference sequence |
| `ncbi_reference_sequence_mane_select_exists` | 是否含 NCBI reference sequence（MANE Select） |
| `approved_gene_symbol` | 批准基因符号（HGNC） |
| `ensembl_id` | Ensembl ID |
| `ensembl_id_select_exists` | 是否含 Ensembl ID（MANE Select） |
| `genbank_nucleotide_sequence` | Genbank nucleotide sequence |
| `protein_sequence` | protein sequence |
| `uniprot_id` | UniProt ID |
| `mgi_id` | MGI ID |
| `mgi_human_disease` | MGI human disease（boolean） |
| `nbk_id` | NBK ID |
| `flybase_id` | FlyBase ID |
| `zfin_id` | ZFIN ID |
| `coriell_disease_name` | Coriell disease name |
| `orphanet_id` / `orphanet_disease_name` | Orphanet |
| `decipher_gene` | DECIPHER gene（boolean） |
| `ghr_type` / `ghr_title` / `ghr_id` | MedlinePlus Genetics |
| `omia_id` / `omia_group` | OMIA |
| `snomedct_id` | SNOMEDCT ID |
| `icd10cm_id` | ICD10CM ID |
| `icd9cm_id` | ICD9CM ID |
| `umls_id` | UMLS ID |
| `disease_ontology_id` | Disease Ontology ID |
| `genetic_alliance_id` | Genetic Alliance ID |
| `gtr` / `kegg_pathways` / `gwas_catalog` | GTR / KEGG / GWAS |
| `clin_gen_dosage` / `clin_gen_validity` | ClinGen |
| `monarch` | Monarch |
| `clinpgx_id` | ClinPGx ID |
| `mondo_id` | MONDO ID |
| `alliance_genome` | Alliance Genome |

> 各外部字段一般都有对应的 `*_exists` 布尔标志位（如 `approved_gene_symbol_exists`、`uniprot_id_exists`）。
> 少量字段标注为 `(currently excluded)`：`locus_specific_database_*`、`decipher_syndrome_*`、`newborn_screening_*`（当前已被排除，不可搜）。

### 2.4 Clinical Synopsis 搜索字段表

`clinicalSynopsis` 索引的字段以 `cs_` 前缀组织，结构与 [entry 字段表](#23-entry-搜索字段表) 中的 `cs_*` 一致。核心字段：

| 字段名 | 描述 |
|--------|------|
| `text` | 默认 text 元字段 |
| `number` | mim number（key field） |
| `prefix` | prefix |
| `title` / `ti_preferred` | 标题 |
| `cs` | clinical synopsis 元字段 |
| `cs_inheritance` | inheritance |
| `cs_growth` | growth 元字段（含 `cs_growth_height` / `cs_growth_weight` / `cs_growth_other`） |
| `cs_head_and_neck` | head and neck 元字段（含 head/face/ears/eyes/nose/mouth/teeth/neck） |
| `cs_cardiovascular` | cardiovascular（含 heart/vascular） |
| `cs_respiratory` | respiratory（含 nasopharynx/larynx/airways/lung） |
| `cs_chest` | chest（含 external features/ribs-ster-num-clavicle-and-scapulae/breasts/diaphragm） |
| `cs_abdomen` | abdomen（含 external features/liver/pancreas/biliary tract/spleen/gastrointestinal） |
| `cs_genitourinary` | genitourinary（含外/内生殖器 male/female、kidneys/ureters/bladder） |
| `cs_skeletal` | skeletal（含 skull/spine/pelvis/limbs/hands/feet） |
| `cs_skin_nails_hair` | skinNailsHair（含 skin/skin histology/skin EM/nails/hair） |
| `cs_muscle_soft_tissue` | muscle/soft tissue |
| `cs_neurologic` | neurologic（含 CNS/PNS/behavioral-psychiatric） |
| `cs_voice` | voice |
| `cs_metabolic_features` | metabolic features |
| `cs_endocrine_features` | endocrine features |
| `cs_hematology` | hematology |
| `cs_immunology` | immunology |
| `cs_neoplasia` | neoplasia |
| `cs_prenatal_manifestations` | prenatal manifestations（含 movement/amniotic fluid/placenta&umbilical cord/maternal/delivery） |
| `cs_laboratory_abnormalities` | laboratory abnormalities |
| `cs_miscellaneous` | miscellaneous |
| `cs_molecular_basis` | molecular basis |
| `cs_date_created` / `cs_date_updated` | 创建/更新日期 |

**本体 ID 字段**（external data，须显式指定）：

| 字段名 | 描述 |
|--------|------|
| `cs_snomedct_id` | SNOMEDCT ID |
| `cs_icd10cm_id` | ICD10CM ID |
| `cs_icd9cm_id` | ICD9CM ID |
| `cs_umls_id` | UMLS ID |
| `cs_hpo_id` | HPO ID |

> 每个 `cs_*` 字段都有对应的 `cs_*_exists` 布尔标志位。

### 2.5 Gene Map 搜索字段表

| 字段名 | 描述 | 备注 |
|--------|------|------|
| `sequence_id` | sequence ID | key field |
| `chromosome` | 染色体 | 1-22, X, Y |
| `chromosome_number` | 染色体号 | 1-22, 23, 24 |
| `chromosome_group` | 染色体组 | A-Autosomal, S-XY |
| `chromosome_location_start` | 起始染色体位置 | 支持 `1:124,300,000` 等坐标语法 |
| `chromosome_location_end` | 结束染色体位置 | |
| `transcript` | transcript | text |
| `cyto_location` | cyto location | 支持 `1p36`、`1p36-p32` 等 |
| `computed_cyto_location` | computed cyto location | |
| `number` | mim number | text |
| `gene_symbol` | gene symbol | text |
| `gene_name` | gene name | text |
| `references` | references | text |
| `comments` | comments | text |
| `molecular_series_number` | 分子系列号 | text |
| `molecular_series_exists` | 是否在分子系列中 | boolean |
| `phenotype_exists` | phenotype 是否存在 | boolean |
| `phenotype` | phenotype | text |
| `phenotype_number` | phenotype mim number | text |
| `phenotypic_series_number` | 表型系列号 | text |
| `phenotypic_series_exists` | 是否在表型系列中 | boolean |
| `phenotype_mapping_key` | 表型映射键 | 1/2/3/4 |
| `phenotype_inheritance` | 遗传方式 | 见 [第 3 节](#3-遗传方式代码表phenotype_inheritance) |
| `imprinting_region_exists` | 是否在印记区 | boolean |
| `gene_id` | NCBI Gene ID | |
| `approved_gene_symbol` | 批准基因符号 | |
| `ensembl_id` | Ensembl ID | |
| `mouse_gene_symbol` | mouse gene symbol | |
| `mouse_mgi_id` | mouse MGI ID | |

---

## 3. 遗传方式代码表（phenotype_inheritance）

`phenotype_inheritance` 字段值域（geneMap 表与搜索中共用）：

| 代码 | 含义 |
|------|------|
| `AD` | Autosomal dominant（常染色体显性） |
| `AR` | Autosomal recessive（常染色体隐性） |
| `PD` | Pseudoautosomal dominant（拟常染色体显性） |
| `PR` | Pseudoautosomal recessive（拟常染色体隐性） |
| `DD` | Digenic dominant（双基因显性） |
| `DR` | Digenic recessive（双基因隐性） |
| `IC` | Isolated cases（散发病例） |
| `ICB` | Inherited chromosomal imbalance（遗传性染色体失衡） |
| `Mi` | Mitochondrial（线粒体） |
| `Mu` | Multifactorial（多因素） |
| `SMo` | Somatic mosaicism（体细胞嵌合） |
| `SMu` | Somatic mutation（体细胞突变） |
| `XL` | X-linked（X 连锁） |
| `XLD` | X-linked dominant（X 连锁显性） |
| `XLR` | X-linked recessive（X 连锁隐性） |
| `YL` | Y-linked（Y 连锁） |

> 本项目 `geneMap` JSON 中的 `Inheritance` 字段即使用这些代码（如 README 示例中的 `"Inheritance": "AD"`）。

---

## 4. 与 API 结合使用

API 的 `entry/search`、`clinicalSynopsis/search`、`geneMap/search` 接口的 `search` / `filter` 参数均使用本文档的语法。

### 4.1 参数对应

| API 参数 | 用途 | 用本文档语法 |
|----------|------|--------------|
| `search` | 主搜索表达式 | 是 |
| `filter` | 过滤器（缩小范围） | 是，常用字段限定 + 布尔 |
| `fields` | 指定搜索字段与权重 | 字段名 + `^权重`，默认 `number^5 title^3 default`（entry）/ `default`（geneMap） |
| `sort` | 排序 | 取搜索字段，必带 `asc`/`desc` |
| `operator` | `AND` 要求全部词 | 等价于给每个词加 `+` |

### 4.2 典型场景与 URL

```bash
API_KEY="your_api_key"
BASE="https://api.omim.org/api"

# (1) 基础文本搜索
curl -s "$BASE/entry/search?search=duchenne+muscular+dystrophy&start=0&limit=20&format=json&apiKey=$API_KEY"

# (2) 字段搜索：按 HGNC 基因符号（external data，须显式字段）
curl -s "$BASE/entry/search?search=approved_gene_symbol:BMPR2&format=json&apiKey=$API_KEY"

# (3) 短语 + prefix 限定（只要表型条目 #）
curl -s "$BASE/entry/search?search=%22pulmonary+hypertension%22+AND+prefix:%23&format=json&apiKey=$API_KEY"

# (4) 布尔：含等位变异的基因条目
curl -s "$BASE/entry/search?search=av_exists:true+AND+prefix:*&format=json&apiKey=$API_KEY"

# (5) 按 PubMed ID 找条目
curl -s "$BASE/entry/search?search=ref_pubmed_id:3294410&format=json&apiKey=$API_KEY"

# (6) 用 filter 过滤：标题含 duchenne 且为 live
curl -s "$BASE/entry/search?search=duchenne&filter=status:live&format=json&apiKey=$API_KEY"

# (7) 通配符前导：搜 *cortisolism
curl -s "$BASE/entry/search?search=%2Acortisolism&format=json&apiKey=$API_KEY"

# (8) Gene Map 按染色体区带
curl -s "$BASE/geneMap/search?search=cyto_location:1p36-p32&format=json&apiKey=$API_KEY"

# (9) Clinical Synopsis 按遗传方式
curl -s "$BASE/clinicalSynopsis/search?search=cs_inheritance:XL&format=json&apiKey=$API_KEY"

# (10) 日期范围：最近一年更新的条目
curl -s "$BASE/entry/search?search=date_updated:lastyear&format=json&apiKey=$API_KEY"
```

> ⚠️ URL 中需对特殊字符做 percent-encoding：
> - 空格 → `+` 或 `%20`
> - `"` → `%22`
> - `#` → `%23`
> - `*` → `%2A`
> - `+` 操作符 → `%2B`
> - `&` → `%26`

### 4.3 Python 中的转义

用 `requests` 时 `params=` 会自动编码，无需手动转义：

```python
import requests

def search_entries(query, limit=20):
    r = requests.get(
        "https://api.omim.org/api/entry/search",
        params={
            "search": query,            # e.g. '"pulmonary hypertension" AND prefix:#'
            "start": 0,
            "limit": limit,
            "format": "json",
        },
        headers={"ApiKey": "your_api_key"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()
```
