---
name: local-carshare-viability-research
description: 住所別カーシェア実用性調査
description_full: Research whether car sharing is practically viable for a specific Japanese address, comparing nearby stations against private car ownership constraints.
version: 1.0.0
triggers:
  - カーシェア 優位性
  - 近所のカーシェアを調べて
  - 車を買うかカーシェアか
  - address-based carshare viability
  - タイムズカー ステーション調査
---

# Local Carshare Viability Research

Use this when kame-dev asks whetherカーシェア is actually practical from a specific Japanese address, especially when comparing against owning a中古軽 or family car.

## Workflow

1. **Ground the address and decision criteria**
   - Extract the exact area/address the user gave.
   - Evaluate not just existence of stations, but practical superiority:
     - walking distance / near-adjacent station
     - number of fallback stations
     - vehicle types suitable for family and shopping
     - reservation risk
     - ability to drive weekly for practice
     - cost vs parking/insurance/vehicle costs

2. **Search multiple sources; official pages are best**
   - Direct official station searches may be hard to automate and search engines may bot-block.
   - Useful fallback query pattern:
     - `Yahoo!検索: <町名> カーシェア タイムズ`
     - `Yahoo!検索: "<station name>"`
   - For Times Car official details, URLs often look like:
     - `https://share.timescar.jp/view/station/detail.jsp?scd=<CODE>`
   - Open official detail pages to verify:
     - station name
     - address
     - vehicle list
     - notes such as bicycle禁止/可, junior seat notes, return instructions

3. **Cross-check other providers**
   - 三井のカーシェアーズ (`carshares.jp`) has prefecture/city station pages. Check whether stations are in the relevant district and whether they are actually close to the user’s address.
   - Do not treat district-level counts as sufficient. If stations are in another subarea (e.g. 下新庄/東中島 while user is in 豊里), mark as backup/not primary.

4. **Assess practical viability**
   - Strong carshare viability if:
     - a station is within a few minutes walking distance or near-adjacent
     - there is at least one family/shopping-suitable vehicle (e.g. ルーミー, フリード, シエンタ)
     - there are multiple fallback vehicles/stations within reasonable distance
   - Weak carshare viability if:
     - only one nearby car and no fallback
     - only small cars unsuitable for family/large shopping
     - station access requires cycling when the station forbids bicycles
     - likely weekend reservation shortage with no alternative

5. **Compare against ownership using realistic monthly costs**
   - For Osaka city residential areas, parking often dominates; use a local estimate if available, otherwise state an assumption.
   - Typical rough ranges used in this case:
     - carshare: 3〜5.5万円/月 depending usage
     - used kei ownership with parking: 5.5〜7万円/月 plus 50〜120万円 initial cash/loan exposure
   - Ownership wins on convenience and practice frequency; carshare wins on fixed-cost and financial risk if nearby access is strong.

## Case-specific finding from 豊里2-2

For 大阪市東淀川区豊里2-2, carshare viability was strong:

- Times Car `UR新豊里`, official code `S678`
  - Address: 大阪市東淀川区豊里2-3
  - Vehicle: ベーシック／ルーミー 1000
  - Very close to 豊里2-2; strong primary station for shopping/family use.
- Times Car `タイムズ豊里`, official code `R858`
  - Address: 豊里4-8
  - Vehicles included MAZDA2, アクアHV, MAZDA3, ライズHV, フリード.
  - Strong fallback; フリード helps family/leisure use.
- Times Car `タイムズ豊里７丁目第２`, official code `V373`
  - Address: 豊里7-4
  - Vehicles: アクアHV x2.
  - Backup candidate.
- 三井のカーシェアーズ had 東淀川区 stations, but they were mainly 下新庄/東中島, so not primary for 豊里2-2.

Conclusion pattern for that case: carshare is clearly worth trying before buying a used kei. Reassess after 1〜2 months if weekend reservations fail, monthly spend exceeds roughly 5万円, or the user needs spontaneous/rainy-day use and frequent driving practice.

## Pitfalls

- Google and DuckDuckGo may bot-block; Yahoo Search sometimes exposes useful local + official links and snippets.
- Bing can show bot challenges or poor local results.
- Do not rely only on map snippets; click official station pages when available to verify current vehicle lineup.
- Be careful with statements like “徒歩何分” unless the route/distance was actually verified. If only address proximity is known, say “かなり近い/近隣” rather than exact minutes.
- Always distinguish “station count in ward” from “stations usable from this address.”
