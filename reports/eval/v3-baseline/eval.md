# Eval Report: v3-baseline

Generated: 2026-05-21T00:22:02Z
Classes: 306  Aug passes: 8  Examples: 2448

## Aggregate Metrics

| Metric | Top-1 | Top-3 |
|---|---|---|
| Exact flag | 93.67% (2293/2448) | 97.47% (2386/2448) |
| Result level | 93.67% (2293/2448) | 97.47% (2386/2448) |

## By Category

| Category | Classes | Top-1 Result | Top-3 Result |
|---|---|---|---|
| national | 255 | 92.40% | 96.96% |
| subnational | 51 | 100.00% | 100.00% |

## By Status

| Status | Classes | Top-1 Result | Top-3 Result |
|---|---|---|---|
| current | 306 | 93.67% | 97.47% |

## By Fictionality

| Fictionality | Classes | Top-1 Result | Top-3 Result |
|---|---|---|---|
| nonfiction | 306 | 93.67% | 97.47% |

## By Variant

| Variant | Classes | Top-1 Result | Top-3 Result |
|---|---|---|---|
| standard | 306 | 93.67% | 97.47% |

## Confusable Groups

### ro-td (result-level, 2 members)

Top-1: 100.0% (16/16)   Top-3: 100.0% (16/16)
Margin stats: min=3.45  mean=4.63  max=5.71  (12/16 computable, 4 not in top-3)

Within-group confusion (top-1):
| True \ Pred | ro | td |
|---|---|---|
| ro | 8 | 0 |
| td | 0 | 8 |

### mc-id (result-level, 2 members)

Top-1: 100.0% (16/16)   Top-3: 100.0% (16/16)
Margin stats: no computable margins (16 correct top-1, no confusable members in top-3)

Within-group confusion (top-1):
| True \ Pred | id | mc |
|---|---|---|
| id | 8 | 0 |
| mc | 0 | 8 |

### ie-ci (result-level, 2 members)

Top-1: 100.0% (16/16)   Top-3: 100.0% (16/16)
Margin stats: min=2.79  mean=4.70  max=6.05  (8/16 computable, 8 not in top-3)

Within-group confusion (top-1):
| True \ Pred | ci | ie |
|---|---|---|
| ci | 8 | 0 |
| ie | 0 | 8 |

### nl-lu (result-level, 2 members)

Top-1: 87.5% (14/16)   Top-3: 100.0% (16/16)
Margin stats: no computable margins (14 correct top-1, no confusable members in top-3)

Within-group confusion (top-1):
| True \ Pred | lu | nl |
|---|---|---|
| lu | 8 | 0 |
| nl | 0 | 6 |

### no-is (result-level, 2 members)

Top-1: 62.5% (10/16)   Top-3: 100.0% (16/16)
Margin stats: no computable margins (10 correct top-1, no confusable members in top-3)

Within-group confusion (top-1):
| True \ Pred | is | no |
|---|---|---|
| is | 8 | 0 |
| no | 0 | 2 |

### au-nz (result-level, 2 members)

Top-1: 50.0% (8/16)   Top-3: 100.0% (16/16)
Margin stats: min=0.27  mean=1.17  max=2.21  (6/8 computable, 2 not in top-3)

Within-group confusion (top-1):
| True \ Pred | au | nz |
|---|---|---|
| au | 2 | 1 |
| nz | 0 | 6 |

### us-states-blue-seal (flag-level, 18 members)

Top-1: 100.0% (144/144)   Top-3: 100.0% (144/144)
Margin stats: min=0.45  mean=4.77  max=7.02  (99/144 computable, 45 not in top-3)

Within-group confusion (top-1):
| True \ Pred | us-id-current | us-ks-current | us-ky-current | us-ma-current | us-me-current | us-mi-current | us-mt-current | us-nd-current | us-ne-current | us-nh-current | us-ny-current | us-or-current | us-pa-current | us-sd-current | us-ut-current | us-va-current | us-vt-current | us-wi-current |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| us-id-current | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| us-ks-current | 0 | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| us-ky-current | 0 | 0 | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| us-ma-current | 0 | 0 | 0 | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| us-me-current | 0 | 0 | 0 | 0 | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| us-mi-current | 0 | 0 | 0 | 0 | 0 | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| us-mt-current | 0 | 0 | 0 | 0 | 0 | 0 | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| us-nd-current | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| us-ne-current | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| us-nh-current | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| us-ny-current | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| us-or-current | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 8 | 0 | 0 | 0 | 0 | 0 | 0 |
| us-pa-current | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 8 | 0 | 0 | 0 | 0 | 0 |
| us-sd-current | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 8 | 0 | 0 | 0 | 0 |
| us-ut-current | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 8 | 0 | 0 | 0 |
| us-va-current | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 8 | 0 | 0 |
| us-vt-current | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 8 | 0 |
| us-wi-current | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 8 |

### us-or-in (flag-level, 2 members)

Top-1: 100.0% (16/16)   Top-3: 100.0% (16/16)
Margin stats: min=3.10  mean=4.77  max=5.69  (15/16 computable, 1 not in top-3)

Within-group confusion (top-1):
| True \ Pred | us-in-current | us-or-current |
|---|---|---|
| us-in-current | 8 | 0 |
| us-or-current | 0 | 8 |

## Per-Class Summary

| class_id | flag_id | result_id | category | exact_top1 | result_top1 |
|---|---|---|---|---|---|
| 0 | ad-current | ad | national | 100.0% | 100.0% |
| 1 | ae-current | ae | national | 100.0% | 100.0% |
| 2 | af-current | af | national | 100.0% | 100.0% |
| 3 | ag-current | ag | national | 100.0% | 100.0% |
| 4 | ai-current | ai | national | 100.0% | 100.0% |
| 5 | al-current | al | national | 100.0% | 100.0% |
| 6 | am-current | am | national | 100.0% | 100.0% |
| 7 | ao-current | ao | national | 100.0% | 100.0% |
| 8 | aq-current | aq | national | 100.0% | 100.0% |
| 9 | ar-current | ar | national | 100.0% | 100.0% |
| 10 | as-current | as | national | 100.0% | 100.0% |
| 11 | at-current | at | national | 100.0% | 100.0% |
| 12 | au-current | au | national | 25.0% | 25.0% |
| 13 | aw-current | aw | national | 100.0% | 100.0% |
| 14 | ax-current | ax | national | 100.0% | 100.0% |
| 15 | az-current | az | national | 100.0% | 100.0% |
| 16 | ba-current | ba | national | 100.0% | 100.0% |
| 17 | bb-current | bb | national | 100.0% | 100.0% |
| 18 | bd-current | bd | national | 100.0% | 100.0% |
| 19 | be-current | be | national | 100.0% | 100.0% |
| 20 | bf-current | bf | national | 87.5% | 87.5% |
| 21 | bg-current | bg | national | 100.0% | 100.0% |
| 22 | bh-current | bh | national | 50.0% | 50.0% |
| 23 | bi-current | bi | national | 100.0% | 100.0% |
| 24 | bj-current | bj | national | 87.5% | 87.5% |
| 25 | bl-current | bl | national | 0.0% | 0.0% |
| 26 | bm-current | bm | national | 100.0% | 100.0% |
| 27 | bn-current | bn | national | 100.0% | 100.0% |
| 28 | bo-current | bo | national | 100.0% | 100.0% |
| 29 | bq-current | bq | national | 75.0% | 75.0% |
| 30 | br-current | br | national | 100.0% | 100.0% |
| 31 | bs-current | bs | national | 100.0% | 100.0% |
| 32 | bt-current | bt | national | 100.0% | 100.0% |
| 33 | bv-current | bv | national | 25.0% | 25.0% |
| 34 | bw-current | bw | national | 100.0% | 100.0% |
| 35 | by-current | by | national | 100.0% | 100.0% |
| 36 | bz-current | bz | national | 100.0% | 100.0% |
| 37 | ca-current | ca | national | 100.0% | 100.0% |
| 38 | cc-current | cc | national | 100.0% | 100.0% |
| 39 | cd-current | cd | national | 100.0% | 100.0% |
| 40 | cf-current | cf | national | 100.0% | 100.0% |
| 41 | cg-current | cg | national | 100.0% | 100.0% |
| 42 | ch-current | ch | national | 100.0% | 100.0% |
| 43 | ci-current | ci | national | 100.0% | 100.0% |
| 44 | ck-current | ck | national | 75.0% | 75.0% |
| 45 | cl-current | cl | national | 100.0% | 100.0% |
| 46 | cm-current | cm | national | 100.0% | 100.0% |
| 47 | cn-current | cn | national | 100.0% | 100.0% |
| 48 | co-current | co | national | 100.0% | 100.0% |
| 49 | cr-current | cr | national | 100.0% | 100.0% |
| 50 | cu-current | cu | national | 100.0% | 100.0% |
| 51 | cv-current | cv | national | 100.0% | 100.0% |
| 52 | cw-current | cw | national | 100.0% | 100.0% |
| 53 | cx-current | cx | national | 100.0% | 100.0% |
| 54 | cy-current | cy | national | 100.0% | 100.0% |
| 55 | cz-current | cz | national | 100.0% | 100.0% |
| 56 | de-current | de | national | 100.0% | 100.0% |
| 57 | dj-current | dj | national | 100.0% | 100.0% |
| 58 | dk-current | dk | national | 100.0% | 100.0% |
| 59 | dm-current | dm | national | 100.0% | 100.0% |
| 60 | do-current | do | national | 100.0% | 100.0% |
| 61 | dz-current | dz | national | 100.0% | 100.0% |
| 62 | ec-current | ec | national | 100.0% | 100.0% |
| 63 | ee-current | ee | national | 100.0% | 100.0% |
| 64 | eg-current | eg | national | 75.0% | 75.0% |
| 65 | eh-current | eh | national | 100.0% | 100.0% |
| 66 | er-current | er | national | 100.0% | 100.0% |
| 67 | es-current | es | national | 100.0% | 100.0% |
| 68 | et-current | et | national | 100.0% | 100.0% |
| 69 | eu-current | eu | national | 100.0% | 100.0% |
| 70 | fi-current | fi | national | 87.5% | 87.5% |
| 71 | fj-current | fj | national | 100.0% | 100.0% |
| 72 | fk-current | fk | national | 100.0% | 100.0% |
| 73 | fm-current | fm | national | 100.0% | 100.0% |
| 74 | fo-current | fo | national | 100.0% | 100.0% |
| 75 | fr-current | fr | national | 12.5% | 12.5% |
| 76 | ga-current | ga | national | 100.0% | 100.0% |
| 77 | gb-current | gb | national | 0.0% | 0.0% |
| 78 | gb-eng-current | gb-eng | national | 100.0% | 100.0% |
| 79 | gb-nir-current | gb-nir | national | 50.0% | 50.0% |
| 80 | gb-sct-current | gb-sct | national | 100.0% | 100.0% |
| 81 | gb-wls-current | gb-wls | national | 100.0% | 100.0% |
| 82 | gd-current | gd | national | 100.0% | 100.0% |
| 83 | ge-current | ge | national | 87.5% | 87.5% |
| 84 | gf-current | gf | national | 0.0% | 0.0% |
| 85 | gg-current | gg | national | 100.0% | 100.0% |
| 86 | gh-current | gh | national | 100.0% | 100.0% |
| 87 | gi-current | gi | national | 100.0% | 100.0% |
| 88 | gl-current | gl | national | 100.0% | 100.0% |
| 89 | gm-current | gm | national | 100.0% | 100.0% |
| 90 | gn-current | gn | national | 100.0% | 100.0% |
| 91 | gp-current | gp | national | 0.0% | 0.0% |
| 92 | gq-current | gq | national | 100.0% | 100.0% |
| 93 | gr-current | gr | national | 100.0% | 100.0% |
| 94 | gs-current | gs | national | 100.0% | 100.0% |
| 95 | gt-current | gt | national | 100.0% | 100.0% |
| 96 | gu-current | gu | national | 100.0% | 100.0% |
| 97 | gw-current | gw | national | 100.0% | 100.0% |
| 98 | gy-current | gy | national | 100.0% | 100.0% |
| 99 | hk-current | hk | national | 100.0% | 100.0% |
| 100 | hm-current | hm | national | 62.5% | 62.5% |
| 101 | hn-current | hn | national | 100.0% | 100.0% |
| 102 | hr-current | hr | national | 100.0% | 100.0% |
| 103 | ht-current | ht | national | 100.0% | 100.0% |
| 104 | hu-current | hu | national | 100.0% | 100.0% |
| 105 | id-current | id | national | 100.0% | 100.0% |
| 106 | ie-current | ie | national | 100.0% | 100.0% |
| 107 | il-current | il | national | 100.0% | 100.0% |
| 108 | im-current | im | national | 100.0% | 100.0% |
| 109 | in-current | in | national | 100.0% | 100.0% |
| 110 | io-current | io | national | 100.0% | 100.0% |
| 111 | iq-current | iq | national | 100.0% | 100.0% |
| 112 | ir-current | ir | national | 100.0% | 100.0% |
| 113 | is-current | is | national | 100.0% | 100.0% |
| 114 | it-current | it | national | 100.0% | 100.0% |
| 115 | je-current | je | national | 100.0% | 100.0% |
| 116 | jm-current | jm | national | 100.0% | 100.0% |
| 117 | jo-current | jo | national | 50.0% | 50.0% |
| 118 | jp-current | jp | national | 100.0% | 100.0% |
| 119 | ke-current | ke | national | 100.0% | 100.0% |
| 120 | kg-current | kg | national | 100.0% | 100.0% |
| 121 | kh-current | kh | national | 100.0% | 100.0% |
| 122 | ki-current | ki | national | 100.0% | 100.0% |
| 123 | km-current | km | national | 100.0% | 100.0% |
| 124 | kn-current | kn | national | 100.0% | 100.0% |
| 125 | kp-current | kp | national | 100.0% | 100.0% |
| 126 | kr-current | kr | national | 100.0% | 100.0% |
| 127 | kw-current | kw | national | 87.5% | 87.5% |
| 128 | ky-current | ky | national | 100.0% | 100.0% |
| 129 | kz-current | kz | national | 100.0% | 100.0% |
| 130 | la-current | la | national | 100.0% | 100.0% |
| 131 | lb-current | lb | national | 100.0% | 100.0% |
| 132 | lc-current | lc | national | 100.0% | 100.0% |
| 133 | li-current | li | national | 100.0% | 100.0% |
| 134 | lk-current | lk | national | 100.0% | 100.0% |
| 135 | lr-current | lr | national | 100.0% | 100.0% |
| 136 | ls-current | ls | national | 100.0% | 100.0% |
| 137 | lt-current | lt | national | 100.0% | 100.0% |
| 138 | lu-current | lu | national | 100.0% | 100.0% |
| 139 | lv-current | lv | national | 100.0% | 100.0% |
| 140 | ly-current | ly | national | 100.0% | 100.0% |
| 141 | ma-current | ma | national | 100.0% | 100.0% |
| 142 | mc-current | mc | national | 100.0% | 100.0% |
| 143 | md-current | md | national | 100.0% | 100.0% |
| 144 | me-current | me | national | 100.0% | 100.0% |
| 145 | mf-current | mf | national | 12.5% | 12.5% |
| 146 | mg-current | mg | national | 100.0% | 100.0% |
| 147 | mh-current | mh | national | 100.0% | 100.0% |
| 148 | mk-current | mk | national | 100.0% | 100.0% |
| 149 | ml-current | ml | national | 100.0% | 100.0% |
| 150 | mm-current | mm | national | 100.0% | 100.0% |
| 151 | mn-current | mn | national | 100.0% | 100.0% |
| 152 | mo-current | mo | national | 100.0% | 100.0% |
| 153 | mp-current | mp | national | 100.0% | 100.0% |
| 154 | mq-current | mq | national | 0.0% | 0.0% |
| 155 | mr-current | mr | national | 100.0% | 100.0% |
| 156 | ms-current | ms | national | 100.0% | 100.0% |
| 157 | mt-current | mt | national | 100.0% | 100.0% |
| 158 | mu-current | mu | national | 100.0% | 100.0% |
| 159 | mv-current | mv | national | 100.0% | 100.0% |
| 160 | mw-current | mw | national | 100.0% | 100.0% |
| 161 | mx-current | mx | national | 100.0% | 100.0% |
| 162 | my-current | my | national | 100.0% | 100.0% |
| 163 | mz-current | mz | national | 100.0% | 100.0% |
| 164 | na-current | na | national | 100.0% | 100.0% |
| 165 | nc-current | nc | national | 0.0% | 0.0% |
| 166 | ne-current | ne | national | 100.0% | 100.0% |
| 167 | nf-current | nf | national | 100.0% | 100.0% |
| 168 | ng-current | ng | national | 100.0% | 100.0% |
| 169 | ni-current | ni | national | 100.0% | 100.0% |
| 170 | nl-current | nl | national | 75.0% | 75.0% |
| 171 | no-current | no | national | 25.0% | 25.0% |
| 172 | np-current | np | national | 100.0% | 100.0% |
| 173 | nr-current | nr | national | 100.0% | 100.0% |
| 174 | nu-current | nu | national | 100.0% | 100.0% |
| 175 | nz-current | nz | national | 75.0% | 75.0% |
| 176 | om-current | om | national | 100.0% | 100.0% |
| 177 | pa-current | pa | national | 100.0% | 100.0% |
| 178 | pe-current | pe | national | 100.0% | 100.0% |
| 179 | pf-current | pf | national | 100.0% | 100.0% |
| 180 | pg-current | pg | national | 100.0% | 100.0% |
| 181 | ph-current | ph | national | 100.0% | 100.0% |
| 182 | pk-current | pk | national | 100.0% | 100.0% |
| 183 | pl-current | pl | national | 100.0% | 100.0% |
| 184 | pm-current | pm | national | 12.5% | 12.5% |
| 185 | pn-current | pn | national | 100.0% | 100.0% |
| 186 | pr-current | pr | national | 100.0% | 100.0% |
| 187 | ps-current | ps | national | 87.5% | 87.5% |
| 188 | pt-current | pt | national | 100.0% | 100.0% |
| 189 | pw-current | pw | national | 100.0% | 100.0% |
| 190 | py-current | py | national | 100.0% | 100.0% |
| 191 | qa-current | qa | national | 100.0% | 100.0% |
| 192 | re-current | re | national | 50.0% | 50.0% |
| 193 | ro-current | ro | national | 100.0% | 100.0% |
| 194 | rs-current | rs | national | 100.0% | 100.0% |
| 195 | ru-current | ru | national | 87.5% | 87.5% |
| 196 | rw-current | rw | national | 100.0% | 100.0% |
| 197 | sa-current | sa | national | 100.0% | 100.0% |
| 198 | sb-current | sb | national | 100.0% | 100.0% |
| 199 | sc-current | sc | national | 100.0% | 100.0% |
| 200 | sd-current | sd | national | 100.0% | 100.0% |
| 201 | se-current | se | national | 100.0% | 100.0% |
| 202 | sg-current | sg | national | 100.0% | 100.0% |
| 203 | sh-current | sh | national | 0.0% | 0.0% |
| 204 | si-current | si | national | 100.0% | 100.0% |
| 205 | sj-current | sj | national | 50.0% | 50.0% |
| 206 | sk-current | sk | national | 87.5% | 87.5% |
| 207 | sl-current | sl | national | 100.0% | 100.0% |
| 208 | sm-current | sm | national | 100.0% | 100.0% |
| 209 | sn-current | sn | national | 100.0% | 100.0% |
| 210 | so-current | so | national | 100.0% | 100.0% |
| 211 | sr-current | sr | national | 100.0% | 100.0% |
| 212 | ss-current | ss | national | 100.0% | 100.0% |
| 213 | st-current | st | national | 100.0% | 100.0% |
| 214 | sv-current | sv | national | 100.0% | 100.0% |
| 215 | sx-current | sx | national | 100.0% | 100.0% |
| 216 | sy-current | sy | national | 100.0% | 100.0% |
| 217 | sz-current | sz | national | 100.0% | 100.0% |
| 218 | tc-current | tc | national | 100.0% | 100.0% |
| 219 | td-current | td | national | 100.0% | 100.0% |
| 220 | tf-current | tf | national | 100.0% | 100.0% |
| 221 | tg-current | tg | national | 100.0% | 100.0% |
| 222 | th-current | th | national | 100.0% | 100.0% |
| 223 | tj-current | tj | national | 100.0% | 100.0% |
| 224 | tk-current | tk | national | 100.0% | 100.0% |
| 225 | tl-current | tl | national | 100.0% | 100.0% |
| 226 | tm-current | tm | national | 100.0% | 100.0% |
| 227 | tn-current | tn | national | 87.5% | 87.5% |
| 228 | to-current | to | national | 100.0% | 100.0% |
| 229 | tr-current | tr | national | 100.0% | 100.0% |
| 230 | tt-current | tt | national | 100.0% | 100.0% |
| 231 | tv-current | tv | national | 100.0% | 100.0% |
| 232 | tw-current | tw | national | 100.0% | 100.0% |
| 233 | tz-current | tz | national | 100.0% | 100.0% |
| 234 | ua-current | ua | national | 100.0% | 100.0% |
| 235 | ug-current | ug | national | 100.0% | 100.0% |
| 236 | um-current | um | national | 75.0% | 75.0% |
| 237 | us-ak-current | us-ak | subnational | 100.0% | 100.0% |
| 238 | us-al-current | us-al | subnational | 100.0% | 100.0% |
| 239 | us-ar-current | us-ar | subnational | 100.0% | 100.0% |
| 240 | us-az-current | us-az | subnational | 100.0% | 100.0% |
| 241 | us-ca-current | us-ca | subnational | 100.0% | 100.0% |
| 242 | us-co-current | us-co | subnational | 100.0% | 100.0% |
| 243 | us-ct-current | us-ct | subnational | 100.0% | 100.0% |
| 244 | us-current | us | national | 25.0% | 25.0% |
| 245 | us-dc-current | us-dc | subnational | 100.0% | 100.0% |
| 246 | us-de-current | us-de | subnational | 100.0% | 100.0% |
| 247 | us-fl-current | us-fl | subnational | 100.0% | 100.0% |
| 248 | us-ga-current | us-ga | subnational | 100.0% | 100.0% |
| 249 | us-hi-current | us-hi | subnational | 100.0% | 100.0% |
| 250 | us-ia-current | us-ia | subnational | 100.0% | 100.0% |
| 251 | us-id-current | us-id | subnational | 100.0% | 100.0% |
| 252 | us-il-current | us-il | subnational | 100.0% | 100.0% |
| 253 | us-in-current | us-in | subnational | 100.0% | 100.0% |
| 254 | us-ks-current | us-ks | subnational | 100.0% | 100.0% |
| 255 | us-ky-current | us-ky | subnational | 100.0% | 100.0% |
| 256 | us-la-current | us-la | subnational | 100.0% | 100.0% |
| 257 | us-ma-current | us-ma | subnational | 100.0% | 100.0% |
| 258 | us-md-current | us-md | subnational | 100.0% | 100.0% |
| 259 | us-me-current | us-me | subnational | 100.0% | 100.0% |
| 260 | us-mi-current | us-mi | subnational | 100.0% | 100.0% |
| 261 | us-mn-current | us-mn | subnational | 100.0% | 100.0% |
| 262 | us-mo-current | us-mo | subnational | 100.0% | 100.0% |
| 263 | us-ms-current | us-ms | subnational | 100.0% | 100.0% |
| 264 | us-mt-current | us-mt | subnational | 100.0% | 100.0% |
| 265 | us-nc-current | us-nc | subnational | 100.0% | 100.0% |
| 266 | us-nd-current | us-nd | subnational | 100.0% | 100.0% |
| 267 | us-ne-current | us-ne | subnational | 100.0% | 100.0% |
| 268 | us-nh-current | us-nh | subnational | 100.0% | 100.0% |
| 269 | us-nj-current | us-nj | subnational | 100.0% | 100.0% |
| 270 | us-nm-current | us-nm | subnational | 100.0% | 100.0% |
| 271 | us-nv-current | us-nv | subnational | 100.0% | 100.0% |
| 272 | us-ny-current | us-ny | subnational | 100.0% | 100.0% |
| 273 | us-oh-current | us-oh | subnational | 100.0% | 100.0% |
| 274 | us-ok-current | us-ok | subnational | 100.0% | 100.0% |
| 275 | us-or-current | us-or | subnational | 100.0% | 100.0% |
| 276 | us-pa-current | us-pa | subnational | 100.0% | 100.0% |
| 277 | us-ri-current | us-ri | subnational | 100.0% | 100.0% |
| 278 | us-sc-current | us-sc | subnational | 100.0% | 100.0% |
| 279 | us-sd-current | us-sd | subnational | 100.0% | 100.0% |
| 280 | us-tn-current | us-tn | subnational | 100.0% | 100.0% |
| 281 | us-tx-current | us-tx | subnational | 100.0% | 100.0% |
| 282 | us-ut-current | us-ut | subnational | 100.0% | 100.0% |
| 283 | us-va-current | us-va | subnational | 100.0% | 100.0% |
| 284 | us-vt-current | us-vt | subnational | 100.0% | 100.0% |
| 285 | us-wa-current | us-wa | subnational | 100.0% | 100.0% |
| 286 | us-wi-current | us-wi | subnational | 100.0% | 100.0% |
| 287 | us-wv-current | us-wv | subnational | 100.0% | 100.0% |
| 288 | us-wy-current | us-wy | subnational | 100.0% | 100.0% |
| 289 | uy-current | uy | national | 100.0% | 100.0% |
| 290 | uz-current | uz | national | 100.0% | 100.0% |
| 291 | va-current | va | national | 100.0% | 100.0% |
| 292 | vc-current | vc | national | 100.0% | 100.0% |
| 293 | ve-current | ve | national | 100.0% | 100.0% |
| 294 | vg-current | vg | national | 100.0% | 100.0% |
| 295 | vi-current | vi | national | 100.0% | 100.0% |
| 296 | vn-current | vn | national | 100.0% | 100.0% |
| 297 | vu-current | vu | national | 100.0% | 100.0% |
| 298 | wf-current | wf | national | 100.0% | 100.0% |
| 299 | ws-current | ws | national | 100.0% | 100.0% |
| 300 | xk-current | xk | national | 100.0% | 100.0% |
| 301 | ye-current | ye | national | 75.0% | 75.0% |
| 302 | yt-current | yt | national | 0.0% | 0.0% |
| 303 | za-current | za | national | 100.0% | 100.0% |
| 304 | zm-current | zm | national | 100.0% | 100.0% |
| 305 | zw-current | zw | national | 100.0% | 100.0% |
