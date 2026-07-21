# OMIM API 调用文档

> 本文档基于 [https://www.omim.org/help/api](https://www.omim.org/help/api) 官方说明整理，面向开发者。
> OMIM API 提供对 OMIM（Online Mendelian Inheritance in Man）数据库的结构化只读访问。

---

## 目录

- [1. 概述](#1-概述)
- [2. 基础（Basics）](#2-基础basics)
  - [2.1 API Key（认证）](#21-api-key认证)
  - [2.2 通用参数](#22-通用参数)
  - [2.3 API HTML 调试界面](#23-api-html-调试界面)
  - [2.4 速率与数量限制](#24-速率与数量限制)
  - [2.5 压缩（gzip）](#25-压缩gzip)
  - [2.6 API 主机](#26-api-主机)
  - [2.7 HTTP 状态码](#27-http-状态码)
- [3. Handlers（数据处理器）](#3-handlers数据处理器)
  - [3.1 `entry` — 条目](#31-entry--条目)
  - [3.2 `clinicalSynopsis` — 临床概要](#32-clinicalsynopsis--临床概要)
  - [3.3 `geneMap` — 基因图谱](#33-genemap--基因图谱)
  - [3.4 `search` — 通用搜索](#34-search--通用搜索)
  - [3.5 `status` — 状态检查](#35-status--状态检查)
  - [3.6 `apiKey` — Key 管理](#36-apikey--key-管理)
- [4. 实用示例](#4-实用示例)
- [5. 与本项目（网页爬虫）的对比与迁移建议](#5-与本项目网页爬虫的对比与迁移建议)

---

## 1. 概述

OMIM API 的 URL 结构非常简单：

```
/api/[handler]?[parameters]
/api/[handler]/[component]?[parameters]
/api/[handler]/[action]?[parameters]
```

| 组成部分 | 说明 | 是否必填 |
|----------|------|----------|
| `handler` | 数据对象类型（entry、clinicalSynopsis、geneMap 等） | 是 |
| `component` | 数据对象内的特定组件（如 references） | 否 |
| `action` | 对数据对象执行的操作（如 search） | 否 |

> 对于基础的 GET 请求，`component` 或 `action` 通常可省略。

**关键约束**：由于数据库是只读的，公开访问仅支持 `GET` 方法，其他 HTTP 方法会返回错误。唯一例外是 `apiKey` handler，它支持 `POST` 和 `DELETE`（用于在浏览器 cookie 中添加/移除 apiKey）。

---

## 2. 基础（Basics）

### 2.1 API Key（认证）

API Key 是分配给每个开发者的唯一密钥，由 OMIM 分配，**不可共享**。每个请求都必须携带它，服务器在处理请求前会先验证 Key。

**三种传递方式**（任选其一）：

| 方式 | 写法 |
|------|------|
| HTTP Header | `ApiKey: nfNEOscLNWWXdSmUoMLPPA` |
| Cookie | `Cookie: ApiKey=nfNEOscLNWWXdSmUoMLPPA` |
| URL 参数 | `https://api.omim.org/...?...&apiKey=nfNEOscLNWWXdSmUoMLPPA` |

> ⚠️ **参数名区分大小写**：是 `apiKey`（小写 p），不是 `apikey` 或 `ApiKey`。

**获取方式**：在 OMIM 官网注册并申请 API Access（[Register for API Access](https://www.omim.org/downloads)）。

### 2.2 通用参数

所有 handler 都支持以下通用参数：

| 参数 | 说明 |
|------|------|
| `format` | 指定返回数据格式，支持 `json` 和 `xml`，例如 `format=json` |

### 2.3 API HTML 调试界面

API 提供了一个基于 HTML 的可视化界面，用于查看 URL 的构造方式：

```
https://api.omim.org/api/html
```

适合调试和探索 API 结构。

### 2.4 速率与数量限制

API 限制单次请求可获取的条目数量：

| 数据类型 | 单请求上限 |
|----------|-----------|
| Entry（条目） | 指定任意 `include` 时：**20 条**；不指定 include：无限制 |
| Clinical Synopsis（临床概要） | 指定任意 `include` 时：**20 条**；不指定 include：无限制 |
| Gene Map（基因图谱） | **100 条** |

**分页**：使用 `start` 和 `limit` 参数分批获取：

```
start=0&limit=20    # 第 1 批
start=20&limit=20   # 第 2 批
start=40&limit=20   # 第 3 批
```

> ⚠️ 超出配额会返回 `429 Too Many Requests`（见 [2.7](#27-http-状态码)）。

### 2.5 压缩（gzip）

API 支持 gzip 压缩。在带宽受限环境下应启用以减少网络流量——压缩可将响应体积减小 **4~5 倍**。

启用方式：在请求中添加 HTTP Header：

```
Accept-Encoding: gzip
```

示例（curl 默认不启用 gzip）：

```bash
# 不压缩
curl "https://api.omim.org/api/..."

# 启用 gzip 压缩
curl -H "Accept-Encoding: gzip" "https://api.omim.org/api/..." | gunzip
```

> 在 Python `requests` 中，gzip 由库自动处理（`requests` 默认发送 `Accept-Encoding: gzip, deflate` 并自动解压）。

### 2.6 API 主机

```
https://api.omim.org
```

### 2.7 HTTP 状态码

| 状态码 | 名称 | 说明 |
|--------|------|------|
| **200** | OK | 请求成功 |
| **400** | Bad Request | URL 错误 |
| **401** | Unauthorized | API Key 无效或未激活 |
| **404** | Not Found | 请求的数据不存在 |
| **429** | Too Many Requests | API Key 的配额已用尽 |
| **500** | Internal Server Error | 服务器内部错误 |

---

## 3. Handlers（数据处理器）

### 3.1 `entry` — 条目

获取单个或多个 OMIM 条目的数据。这是最常用的 handler。

#### 3.1.1 基本请求

**必需参数**：`mimNumber`（指定要获取的 MIM 条目）

```
https://api.omim.org/api/entry?mimNumber=100100
```

**多个 MIM 号**（两种写法）：

```
https://api.omim.org/api/entry?mimNumber=100100&mimNumber=100200
https://api.omim.org/api/entry?mimNumber=100100,100200
```

**默认返回内容**：MIM number、prefix、status、titles。其他内容通过 `include` 参数获取。

#### 3.1.2 `include` 参数（包含的内容）

| include 值 | 说明 |
|------------|------|
| `text` | 文本字段小节 |
| `existFlags` | exists 标志位（clinical synopsis / allelic variant / gene map / phenotype map 是否存在） |
| `allelicVariantList` | 等位基因变异列表 |
| `clinicalSynopsis` | 临床概要 |
| `seeAlso` | see also 字段 |
| `referenceList` | 参考文献列表 |
| `geneMap` | 基因图谱 / 表型图谱数据 |
| `externalLinks` | 外部数据库链接 |
| `contributors` | 贡献者字段 |
| `creationDate` | 创建日期字段 |
| `editHistory` | 编辑历史字段 |
| `dates` | 日期数据 |
| `all` | 包含以上所有数据 |

> 💡 官方建议：**只请求所需的数据**。检索不需要的数据会拖慢请求速度。

可同时指定多个 include（两种写法）：

```
https://api.omim.org/api/entry?mimNumber=100100&include=text&include=geneMap
https://api.omim.org/api/entry?mimNumber=100100&include=text,geneMap
```

#### 3.1.3 `text` 的 section 过滤

默认 `text` include 会返回全部文本（可能很长）。可在 `text` 后加冒号 `:` 指定返回某个小节：

```
https://api.omim.org/api/entry?mimNumber=100100&include=text:clinicalFeatures
```

**可用的 text section 名称**：

| Section 名称 | 标题 |
|--------------|------|
| `animalModel` | Animal Model |
| `biochemicalFeatures` | Biochemical Features |
| `clinicalFeatures` | Clinical Features |
| `clinicalManagement` | Clinical Management |
| `cloning` | Cloning and Expression |
| `cytogenetics` | Cytogenetics |
| `description` | Description |
| `diagnosis` | Diagnosis |
| `evolution` | Evolution |
| `geneFamily` | Gene Family |
| `geneFunction` | Gene Function |
| `geneStructure` | Gene Structure |
| `geneTherapy` | Gene Therapy |
| `geneticVariability` | Genetic Variability |
| `genotype` | Genotype |
| `genotypePhenotypeCorrelations` | Genotype/Phenotype Correlations |
| `heterogeneity` | Heterogeneity |
| `history` | History |
| `inheritance` | Inheritance |
| `mapping` | Mapping |
| `molecularGenetics` | Molecular Genetics |
| `nomenclature` | Nomenclature |
| `otherFeatures` | Other Features |
| `pathogenesis` | Pathogenesis |
| `phenotype` | Phenotype |
| `populationGenetics` | Population Genetics |
| `text` | Text（条目开头未分段的文本） |

**获取全部数据**：

```
https://api.omim.org/api/entry?mimNumber=100100&include=all
```

#### 3.1.4 `exclude` 参数

`exclude` 用于排除不需要的小节。例如：要除临床概要外的全部数据：

```
https://api.omim.org/api/entry?mimNumber=100100&include=all&exclude=clinicalSynopsis
```

#### 3.1.5 search 动作（条目搜索）

搜索基于 **Apache SOLR**，使用 extended dismax parser。

> 📖 **搜索语法与完整字段表见 [`docs/OMIM_Search_Help.md`](./OMIM_Search_Help.md)**。`search` / `filter` 参数支持布尔、字段限定（如 `approved_gene_symbol:BMPR2`、`prefix:#`、`ref_pubmed_id:123`）、通配符、短语、日期范围、cytoband 坐标等。下文仅列 API 参数；具体查询串怎么写请参考该文档。

```
https://api.omim.org/api/entry/search?search=duchenne&start=0&limit=20
```

| 参数 | 说明 |
|------|------|
| `search` | 搜索词（**必填**） |
| `filter` | 过滤器（可选） |
| `fields` | 搜索字段，默认 `number^5 title^3 default` |
| `sort` | 排序，默认 `score desc` |
| `operator` | 操作符，`AND` 表示要求返回文档包含所有搜索词 |
| `start` | 结果起始偏移，默认 0 |
| `limit` | 返回结果数，默认 10 |
| `retrieve` | 检索对应数据而非条目本身：`geneMap` 或 `clinicalSynopsis` |

**search 可与其他参数组合**：

```
https://api.omim.org/api/entry/search?search=duchenne&start=0&limit=20&include=geneMap
```

**`operator` 参数**：

| 值 | 说明 |
|----|------|
| `AND` | 要求返回文档包含所有搜索词 |

**`sort` 参数**（取 entry 索引中的搜索字段）：

| 排序值 | 说明 |
|--------|------|
| `score desc` | 按相关度降序（默认） |
| `score desc, prefix_sort desc` | 相关度降序 + prefix 降序 |
| `date_created desc` | 按创建日期降序 |
| `date_created asc` | 按创建日期升序 |
| `date_updated desc` | 按更新日期降序 |
| `date_updated asc` | 按更新日期升序 |

```
https://api.omim.org/api/entry/search?search=duchenne&sort=score+desc
```

> ⚠️ 排序方向（`asc` 或 `desc`）是必填的。未指定时默认 `score desc`。

**`retrieve` 参数**：检索对应数据而非条目本身：

| 值 | 说明 |
|----|------|
| `geneMap` | 检索对应的基因图谱 |
| `clinicalSynopsis` | 检索对应的临床概要 |

> 💡 搜索也可通过 `search` handler 进行，此时 handler 与 action 互换位置，两者等价：
> ```
> /api/entry/search?search=duchenne  ≡  /api/search/entry?search=duchenne
> ```

#### 3.1.6 `allelicVariantList` 组件

获取指定 MIM 条目的等位基因变异列表：

```
https://api.omim.org/api/entry/allelicVariantList?mimNumber=100100
```

#### 3.1.7 `referenceList` 组件

获取指定 MIM 条目的参考文献列表：

```
https://api.omim.org/api/entry/referenceList?mimNumber=100100
```

#### 3.1.8 Entry 数据字段（响应结构）

```
omim
└── entryList
    └── entry
        ├── prefix
        ├── mimNumber
        ├── titles
        │   ├── preferredTitle          # 标题与符号，以 ';' 分隔
        │   └── includedTitles          # 标题以 ';;' 分隔，标题/符号以 ';' 分隔
        ├── status                      # 'live' | 'moved' | 'removed'
        ├── movedTo                     # 若条目被移动，设为目标 MIM 号
        ├── clinicalSynopsisExists      # true|false（需设置 existFlags include）
        ├── allelicVariantExists        # true|false（需设置 existFlags include）
        ├── geneMapExists               # true|false（需设置 existFlags include）
        ├── phenotypeMapExists          # true|false（需设置 existFlags include）
        ├── phenotypicSeriesExists      # true|false（需设置 existFlags include）
        ├── textSectionList             # 文本小节列表（顺序）
        │   └── textSection
        │       ├── textSectionName
        │       ├── textSectionTitle
        │       └── textSectionContent
        ├── allelicVariantList
        │   └── allelicVariant
        │       ├── number
        │       ├── status              # 'live' | 'moved' | 'removed'
        │       ├── movedTo
        │       ├── name
        │       ├── alternativeNames
        │       ├── mutations
        │       ├── text
        │       ├── clinvarAccessions   # ClinVar accession 逗号分隔列表
        │       ├── dbSnps              # dbSNP 逗号分隔列表
        │       ├── gnomadSnps          # gnomAD SNPs
        │       └── seeAlso             # see-also 列表，以 ';' 分隔
        ├── referenceList
        │   └── reference
        │       ├── mimNumber
        │       ├── referenceNumber
        │       ├── authors
        │       ├── title
        │       ├── source
        │       ├── pubmedID
        │       ├── articleUrl
        │       └── doi
        ├── geneMapList
        │   └── geneMap
        │       ├── sequenceID
        │       ├── chromosome          # 1-24
        │       ├── chromosomeSymbol    # 1-22, X, Y
        │       ├── chromosomeSort
        │       ├── chromosomeLocationStart   # 可选
        │       ├── chromosomeLocationEnd     # 可选
        │       ├── transcript               # 可选
        │       ├── cytoLocation
        │       ├── computedCytoLocation     # 可选
        │       ├── mimNumber
        │       ├── molecularSeriesNumber    # 分子系列号，逗号分隔
        │       ├── geneSymbols              # 基因符号，逗号分隔
        │       ├── geneName
        │       ├── references
        │       ├── comments
        │       ├── mouseGeneSymbol
        │       ├── mouseMgiID
        │       ├── approvedGeneSymbols
        │       ├── geneIDs
        │       ├── ensemblIDs
        │       └── phenotypeMapList
        │           └── phenotypeMap   (见下)
        ├── phenotypeMapList
        │   └── phenotypeMap
        │       ├── mimNumber
        │       ├── phenotype
        │       ├── phenotypeMimNumber
        │       ├── phenotypicSeriesNumber   # 逗号分隔列表
        │       ├── phenotypeMappingKey
        │       └── phenotypeInheritance
        ├── externalLinks
        │   ├── geneIDs                   # entrez gene ID，逗号分隔
        │   ├── hgncID                     # HGNC ID
        │   ├── ensemblIDs                 # 三冒号分隔的逗号分隔 ensembl ID 对
        │   ├── approvedGeneSymbols        # 逗号分隔
        │   ├── ncbiReferenceSequences
        │   ├── genbankNucleotideSequences
        │   ├── proteinSequences
        │   ├── uniProtIDs
        │   ├── locusSpecificDBs           # 三分号分隔的 name/url 元组
        │   ├── mgiIDs
        │   ├── mgiHumanDisease            # true|false
        │   ├── nbkIDs                     # NBK ID/临床疾病名 对
        │   ├── flybaseIDs
        │   ├── zfinIDs
        │   ├── coriellDiseases
        │   ├── orphanetDiseases           # orphanet ID/疾病名 对
        │   ├── decipherSyndromes
        │   ├── decipherGene               # true|false
        │   ├── geneticsHomeReferenceIDs
        │   ├── omiaIDs
        │   ├── snomedctIDs
        │   ├── icd10cmIDs
        │   ├── icd9cmIDs
        │   ├── umlsIDs
        │   ├── diseaseOntologyIDs
        │   ├── geneticAllianceIDs
        │   ├── gtr
        │   ├── keggPathways
        │   ├── gwasCatalog
        │   ├── clinGenDosage
        │   ├── clinGenValidity
        │   ├── monarch
        │   ├── newbornScreening
        │   ├── clinpgxID
        │   ├── mondoID
        │   └── allianceGenome
        ├── contributors
        ├── creationDate
        ├── editHistory
        ├── dateCreated                   # Web 日期
        ├── epochCreated                  # Unix 时间戳
        ├── dateUpdated                   # Web 日期
        └── epochUpdated                  # Unix 时间戳
```

#### 3.1.9 Entry Allelic Variant 数据字段

```
omim
└── allelicVariantLists
    └── allelicVariantList
        └── allelicVariant
            ├── prefix
            ├── mimNumber
            ├── preferredTitle
            ├── number
            ├── status              # 'live' | 'moved' | 'removed'
            ├── movedTo
            ├── name
            ├── alternativeNames
            ├── mutations
            ├── text
            └── dbSnps              # dbSNP 逗号分隔列表
```

#### 3.1.10 Entry Reference 数据字段

```
omim
└── referenceLists
    └── referenceList
        └── reference
            ├── mimNumber
            ├── referenceNumber
            ├── authors
            ├── title
            ├── source
            ├── pubmedID
            ├── articleUrl
            └── doi
```

---

### 3.2 `clinicalSynopsis` — 临床概要

#### 3.2.1 基本请求

**必需参数**：`mimNumber`

```
https://api.omim.org/api/clinicalSynopsis?mimNumber=100100
```

**多个 MIM 号**：

```
https://api.omim.org/api/clinicalSynopsis?mimNumber=100100&mimNumber=100200
https://api.omim.org/api/clinicalSynopsis?mimNumber=100100,100200
```

默认返回 MIM number、prefix、status、titles。

#### 3.2.2 `include` 参数

| include 值 | 说明 |
|------------|------|
| `clinicalSynopsis` | 临床概要 |
| `existFlags` | exists 标志位 |
| `externalLinks` | 外部链接 |
| `contributors` | 贡献者 |
| `creationDate` | 创建日期 |
| `editHistory` | 编辑历史 |
| `dates` | 日期数据 |
| `all` | 以上全部 |

```
https://api.omim.org/api/clinicalSynopsis?mimNumber=100100&include=clinicalSynopsis&include=externalLinks
https://api.omim.org/api/clinicalSynopsis?mimNumber=100100&include=clinicalSynopsis,externalLinks
https://api.omim.org/api/clinicalSynopsis?mimNumber=100100&include=all
https://api.omim.org/api/clinicalSynopsis?mimNumber=100100&include=all&exclude=externalLinks
```

#### 3.2.3 search 动作

```
https://api.omim.org/api/clinicalSynopsis/search?search=disorder&start=0&limit=20
```

| 参数 | 说明 |
|------|------|
| `search` | 搜索词（必填） |
| `filter` | 过滤器（可选） |
| `fields` | 搜索字段，默认 `number^5 title^3 default` |
| `sort` | 排序，默认 `score desc` |
| `start` | 起始偏移，默认 0 |
| `limit` | 返回数，默认 10 |

**`sort` 参数**：

| 排序值 | 说明 |
|--------|------|
| `score desc` | 相关度降序（默认） |
| `score desc, prefix_sort desc` | 相关度 + prefix 降序 |
| `date_created desc` / `asc` | 创建日期降序/升序 |
| `date_updated desc` / `asc` | 更新日期降序/升序 |

> ⚠️ 排序方向（`asc`/`desc`）必填。
>
> 💡 等价写法：`/api/clinicalSynopsis/search` ≡ `/api/search/clinicalSynopsis`

#### 3.2.4 Clinical Synopsis 数据字段（响应结构）

```
omim
└── clinicalSynopsisList
    └── clinicalSynopsis
        ├── mimNumber
        ├── prefix
        ├── preferredTitle
        ├── inheritance               # 所有字段中的特征以 ';' 分隔，含 UMLS/SNOMEDCT/ICD10CM/ICD9CM/HPO ID
        ├── growth
        │   ├── growthHeight
        │   ├── growthWeight
        │   └── growthOther
        ├── headAndNeck
        │   ├── headAndNeckHead / headAndNeckFace / headAndNeckEars
        │   ├── headAndNeckEyes / headAndNeckNose
        │   ├── headAndNeckMouth / headAndNeckTeeth / headAndNeckNeck
        ├── cardiovascular
        │   ├── cardiovascularHeart
        │   └── cardiovascularVascular
        ├── respiratory
        │   ├── respiratoryNasopharynx / respiratoryLarynx
        │   ├── respiratoryAirways / respiratoryLung
        ├── chest
        │   ├── chestExternalFeatures / chestRibsSternumClaviclesAndScapulae
        │   ├── chestBreasts / chestDiaphragm
        ├── abdomen
        │   ├── abdomenExternalFeatures / abdomenLiver / abdomenPancreas
        │   ├── abdomenBiliaryTract / abdomenSpleen / abdomenGastrointestinal
        ├── genitourinary
        │   ├── genitourinaryExternalGenitaliaMale / genitourinaryExternalGenitaliaFemale
        │   ├── genitourinaryInternalGenitaliaMale / genitourinaryInternalGenitaliaFemale
        │   ├── genitourinaryKidneys / genitourinaryUreters / genitourinaryBladder
        ├── skeletal
        │   ├── skeletalSkull / skeletalSpine / skeletalPelvis
        │   ├── skeletalLimbs / skeletalHands / skeletalFeet
        ├── skinNailsHair
        │   ├── skinNailsHairSkin / skinNailsHairSkinHistology
        │   ├── skinNailsHairSkinElectronMicroscopy / skinNailsHairNails / skinNailsHairHair
        ├── muscleSoftTissue
        ├── neurologic
        │   ├── neurologicCentralNervousSystem / neurologicPeripheralNervousSystem
        │   └── neurologicBehavioralPsychiatricManifestations
        ├── voice
        ├── metabolicFeatures
        ├── endocrineFeatures
        ├── hematology
        ├── immunology
        ├── neoplasia
        ├── prenatalManifestations
        │   ├── prenatalManifestationsMovement / prenatalManifestationsAmnioticFluid
        │   ├── prenatalManifestationsPlacentaAndUmbilicalCord / prenatalManifestationsMaternal
        │   └── prenatalManifestationsDelivery
        ├── laboratoryAbnormalities
        ├── miscellaneous
        ├── molecularBasis
        ├── [字段]Exists 系列            # 每个字段有对应的 Exists 标志位（见下）
        ├── oldFormat                    # 旧格式临床概要，会重映射为新格式
        ├── externalLinks                # 见 [3.1.8](#318-entry-数据字段响应结构)
        ├── contributors
        ├── creationDate
        ├── editHistory
        ├── dateCreated / epochCreated
        └── dateUpdated / epochUpdated
```

**Exists 标志位**（每个字段对应一个，表示是否含数据）：
- (i) 一级：`inheritanceExists`, `growthExists`, `headAndNeckExists`, `cardiovascularExists`, `respiratoryExists`, `chestExists`, `abdomenExists`, `genitourinaryExists`, `skeletalExists`, `skinNailsHairExists`, `neurologicExists`, `prenatalManifestationsExists`, `laboratoryAbnormalitiesExists`
- (ii) 二级：`growthHeightExists`, `growthWeightExists`, `growthOtherExists`, `headAndNeckHeadExists`, `headAndNeckFaceExists`, `headAndNeckEarsExists`, `headAndNeckEyesExists`, `headAndNeckNoseExists`, `headAndNeckMouthExists`, `headAndNeckTeethExists`, `headAndNeckNeckExists`, `cardiovascularHeartExists`, `cardiovascularVascularExists`, `respiratoryNasopharynxExists`, `respiratoryLarynxExists`, `respiratoryAirwaysExists`, `respiratoryLungExists`, `chestExternalFeaturesExists`, `chestRibsSternumClaviclesAndScapulaeExists`, `chestBreastsExists`, `chestDiaphragmExists`, `abdomenExternalFeaturesExists`, `abdomenLiverExists`, `abdomenPancreasExists`, `abdomenBiliaryTractExists`, `abdomenSpleenExists`, `abdomenGastrointestinalExists`, `genitourinaryExternalGenitaliaMaleExists`, `genitourinaryExternalGenitaliaFemaleExists`, `genitourinaryInternalGenitaliaMaleExists`, `genitourinaryInternalGenitaliaFemaleExists`, `genitourinaryKidneysExists`, `genitourinaryUretersExists`, `genitourinaryBladderExists`, `skeletalSkullExists`, `skeletalSpineExists`, `skeletalPelvisExists`, `skeletalLimbsExists`, `skeletalHandsExists`, `skeletalFeetExists`, `skinNailsHairSkinExists`, `skinNailsHairSkinHistologyExists`, `skinNailsHairSkinElectronMicroscopyExists`, `skinNailsHairNailsExists`, `skinNailsHairHairExists`, `muscleSoftTissueExists`, `neurologicCentralNervousSystemExists`, `neurologicPeripheralNervousSystemExists`, `neurologicBehavioralPsychiatricManifestationsExists`, `voiceExists`, `metabolicFeaturesExists`, `endocrineFeaturesExists`, `hematologyExists`, `immunologyExists`, `neoplasiaExists`, `prenatalManifestationsMovementExists`, `prenatalManifestationsAmnioticFluidExists`, `prenatalManifestationsPlacentaAndUmbilicalCordExists`, `prenatalManifestationsMaternalExists`, `prenatalManifestationsDeliveryExists`, `miscellaneousExists`, `molecularBasisExists`

---

### 3.3 `geneMap` — 基因图谱

#### 3.3.1 基本请求

支持三种检索参数：

| 参数 | 说明 |
|------|------|
| `sequenceID` | 基因图谱中的 sequence ID（连续整数，无间断，**仅当日内稳定**） |
| `mimNumber` | MIM 号 |
| `chromosome` | 染色体：1-22, 23(X), 24(Y), 25(M), X, Y, M(线粒体), A(常染色体组), S(XY 组) |
| `chromosomeSort` | `chromosome` 的子参数，染色体内的排序（**仅当日内稳定**） |

**`sequenceID` 和 `chromosome`/`chromosomeSort` 支持分页参数**：

| 参数 | 说明 |
|------|------|
| `start` | 起始偏移，默认 0（基于 sequence ID 时可为负数） |
| `limit` | 返回条目数，默认 10 |

**`phenotypeExists` 过滤**：

| 值 | 说明 |
|----|------|
| `true` | 仅返回有表型的条目 |
| `false` | 仅返回无表型的条目 |
| 默认 | 返回全部 |

#### 3.3.2 示例

按 mimNumber：

```
https://api.omim.org/api/geneMap?mimNumber=100100
https://api.omim.org/api/geneMap?mimNumber=100100&mimNumber=100200
https://api.omim.org/api/geneMap?mimNumber=100100,100200
```

按 sequenceID：

```
https://api.omim.org/api/geneMap?sequenceID=10                          # 第 10 号
https://api.omim.org/api/geneMap?sequenceID=10&limit=10                 # 从第 10 号起取 10 条
https://api.omim.org/api/geneMap?sequenceID=20&limit=10                 # 取后续 10 条
https://api.omim.org/api/geneMap?sequenceID=20&start=-4&limit=10        # start 可为负
```

按染色体：

```
https://api.omim.org/api/geneMap?chromosome=1&start=0&limit=10          # 1 号染色体前 10 条
https://api.omim.org/api/geneMap?chromosome=1&start=10&limit=10         # 后续 10 条
```

按 chromosomeSort：

```
https://api.omim.org/api/geneMap?chromosome=1&chromosomeSort=1&limit=10
https://api.omim.org/api/geneMap?chromosome=1&chromosomeSort=10&limit=10
https://api.omim.org/api/geneMap?chromosome=1&chromosomeSort=1&start=1&limit=10
```

> ⚠️ `sequenceID` 和 `chromosomeSort` **仅在当日内稳定**（基因图谱每日更新），不可跨天复用。

#### 3.3.3 search 动作

```
https://api.omim.org/api/geneMap/search?search=kinase&start=0&limit=20
```

| 参数 | 说明 |
|------|------|
| `search` | 搜索词（必填） |
| `filter` | 过滤器（可选） |
| `fields` | 搜索字段，默认 `default` |
| `sort` | 排序，默认 `score desc` |
| `start` / `limit` | 分页，默认 0 / 10 |

**`sort` 参数**：

| 排序值 | 说明 |
|--------|------|
| `score desc` | 相关度降序（默认） |
| `chromosome_number asc` | 染色体号升序 |
| `chromosome_number asc, chromosome_location_start asc` | 染色体号 + 起始位置升序 |

> ⚠️ 排序方向必填。等价写法：`/api/geneMap/search` ≡ `/api/search/geneMap`

#### 3.3.4 Gene Map 数据字段（响应结构）

```
omim
└── listResponse
    ├── chromosome          # 1-24
    ├── chromosomeSymbol    # 1-22, X, Y
    ├── totalResults
    ├── startIndex
    ├── endIndex
    └── geneMapList
        └── geneMap
            ├── sequenceID
            ├── chromosome          # 1-24
            ├── chromosomeSymbol    # 1-22, X, Y
            ├── chromosomeSort
            ├── chromosomeLocationStart   # 可选
            ├── chromosomeLocationEnd     # 可选
            ├── transcript               # 可选
            ├── cytoLocation
            ├── computedCytoLocation     # 可选
            ├── mimNumber
            ├── molecularSeriesNumber    # 分子系列号，逗号分隔
            ├── geneSymbols              # 逗号分隔
            ├── geneName
            ├── references
            ├── comments
            ├── mouseGeneSymbol
            ├── mouseMgiID
            ├── approvedGeneSymbols
            ├── geneIDs
            ├── ensemblIDs
            └── phenotypeMapList
                └── phenotypeMap
                    ├── mimNumber
                    ├── phenotype
                    ├── phenotypeMimNumber
                    ├── phenotypicSeriesNumber   # 逗号分隔
                    ├── phenotypeMappingKey
                    └── phenotypeInheritance
```

---

### 3.4 `search` — 通用搜索

`search` handler 用于搜索，其行为已在上文四个 handler 的 search 动作中说明。把 handler 与 action 互换即可：

| 写法 | 等价于 |
|------|--------|
| `/api/search/entry?search=...` | `/api/entry/search?search=...` |
| `/api/search/geneMap?search=...` | `/api/geneMap/search?search=...` |
| `/api/search/clinicalSynopsis?search=...` | `/api/clinicalSynopsis/search?search=...` |

#### Search 响应数据字段

```
omim
└── searchResponse
    ├── search
    │   ├── expandedSearch
    │   ├── parsedSearch
    │   ├── searchSuggestion
    │   └── searchSpelling
    ├── filter
    │   └── expandedFilter
    ├── fields
    ├── searchReport
    ├── totalResults
    ├── startIndex
    ├── endIndex
    ├── sort
    ├── searchTime
    └── *List                       # entry/clinicalSynopsis/geneMap/phenotypeMap 列表
```

---

### 3.5 `status` — 状态检查

检查 API 状态：

```
https://api.omim.org/api/status
```

---

### 3.6 `apiKey` — Key 管理

> ⚠️ 此 handler 仅用于支持 API HTML 界面，把 API Key 设置到浏览器 cookie 中，普通开发者一般不用。

| 参数 | 说明 |
|------|------|
| `apiKey` | API Key |

设置 cookie（仅 `POST`）：

```
https://api.omim.org/api/apiKey?apiKey=foo
```

移除 cookie（仅 `DELETE`）：

```
https://api.omim.org/api/apiKey
```

---

## 4. 实用示例

### 4.1 curl 示例

```bash
# 设置变量
API_KEY="your_api_key_here"
BASE="https://api.omim.org/api"

# (1) 获取单个条目的全部数据
curl -s "$BASE/entry?mimNumber=100100&include=all&format=json&apiKey=$API_KEY"

# (2) 仅获取特定 text section（gzip 压缩）
curl -s -H "Accept-Encoding: gzip" \
  "$BASE/entry?mimNumber=100100&include=text:clinicalFeatures&format=json&apiKey=$API_KEY" | gunzip

# (3) 批量获取多个条目（注意 include 时上限 20）
curl -s "$BASE/entry?mimNumber=100100,100200&include=geneMap&format=json&apiKey=$API_KEY"

# (4) 用 Header 传递 Key（推荐，避免泄露在日志中）
curl -s -H "ApiKey: $API_KEY" "$BASE/entry?mimNumber=100100&include=clinicalSynopsis"

# (5) 搜索条目
curl -s "$BASE/entry/search?search=duchenne&start=0&limit=20&format=json&apiKey=$API_KEY"

# (6) 获取等位变异列表
curl -s "$BASE/entry/allelicVariantList?mimNumber=100100&format=json&apiKey=$API_KEY"

# (7) 按染色体获取基因图谱（每批 100）
curl -s "$BASE/geneMap?chromosome=1&start=0&limit=100&format=json&apiKey=$API_KEY"

# (8) 检查 API 状态
curl -s "$BASE/status"
```

### 4.2 Python（requests）示例

```python
import requests

BASE = "https://api.omim.org/api"
API_KEY = "your_api_key_here"

def fetch(path, params=None):
    params = params or {}
    params.setdefault("format", "json")
    headers = {"ApiKey": API_KEY}          # 用 Header 传 Key，不进 URL/日志
    r = requests.get(BASE + path, params=params, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()

# (1) 单条目全部数据
data = fetch("/entry", {"mimNumber": 100100, "include": "all"})
entry = data["omim"]["entryList"][0]["entry"]
print(entry["titles"]["preferredTitle"])

# (2) 特定 text section
data = fetch("/entry", {"mimNumber": 100100, "include": "text:clinicalFeatures"})

# (3) 分页搜索（自动翻页示例）
def search_entries(query, limit=20):
    start = 0
    while True:
        data = fetch("/entry/search",
                     {"search": query, "start": start, "limit": limit})
        resp = data["omim"]["searchResponse"]
        results = resp["search"]["response"] if False else None  # 视返回结构调整
        total = int(resp.get("totalResults", 0))
        # ... 处理本批结果 ...
        start += limit
        if start >= total:
            break

# (4) 等位变异
variants = fetch("/entry/allelicVariantList", {"mimNumber": 100100})

# (5) 基因图谱（按染色体，分页 100）
gm = fetch("/geneMap", {"chromosome": 1, "start": 0, "limit": 100})
```

### 4.3 关键注意事项

1. **Key 安全**：优先用 `ApiKey` HTTP Header 传递，避免把 Key 写进 URL（会出现在服务器/代理日志中）。
2. **include 上限**：带任何 `include` 的 entry / clinicalSynopsis 请求，单次最多 20 条。批量时用 `start`+`limit` 分页。
3. **排序方向必填**：`sort` 参数必须带 `asc`/`desc`。
4. **sequenceID / chromosomeSort 不稳定**：仅当日有效，隔天会变。
5. **gzip**：带宽受限时启用 `Accept-Encoding: gzip`（requests 自动处理）。
6. **只读**：仅 GET（apiKey 的 POST/DELETE 除外）。
7. **错误处理**：重点关注 401（Key 无效）、404（无数据）、429（配额超限）。

---

## 5. 数据来源与架构

本项目自 v2.0 起 exclusively 使用 **OMIM 官方渠道**获取数据：

1. **官方文本文件**（`omim-cli download`）：`mimTitles.txt`、`genemap2.txt`、`morbidmap.txt`、`mim2gene.txt`。提供结构化的基因-表型映射、标题、类型等基础数据，无需 per-entry API 调用。
2. **OMIM REST API**（`omim-cli update --with-api`）：在文本文件基础上，通过 `entry?include=all` 补充文本小节、临床概要、等位变异、参考文献、externalLinks 等深度内容。

旧版 HTML 爬虫（BeautifulSoup + `mirror.omim.org`）已在 v2.0 移除，原因：
- HTML 页面结构变化会导致解析断裂，维护成本高
- 违反 OMIM 用户协议的风险
- API 提供更完整、更稳定的结构化数据

### 5.1 API 与文本文件的分工

| 数据域 | 来源 | 说明 |
|--------|------|------|
| prefix / title / mim_type / gene identifiers | 文本文件 | 权威来源，每日更新 |
| geneMap / phenotypeMap | 文本文件 | 权威来源，包含染色体位置和遗传方式 |
| phenotypic_series | 文本文件派生 | 从 geneMap 的 Phenotype MIM number 推导 |
| text_sections / clinical_synopsis | API `include=all` | 文本文件不含这些深度内容 |
| allelic_variants / references | API `include=all` | 仅 API 提供 |
| externalLinks / editHistory / dates | API `include=all` | v2.1 新增，30+ 外部数据库 cross-ref |
| status / moved_to | API `include=all` | 条目迁移/删除状态 |

### 5.2 --refresh 增量更新

`omim-cli update --refresh` 通过 API 的 `include=dates` 轻量探测每条目的 `dateUpdated`，仅对 OMIM 侧已变更的条目重新拉取全量数据，避免重复消耗配额。
