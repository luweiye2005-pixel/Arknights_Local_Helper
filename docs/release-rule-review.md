# 正式发布藏品规则复核清单

> 本文由 `scripts/audit_release_rules.py` 生成，只列出不能安全自动迁移的旧解析规则。

- 待复核藏品：118 件
- 待复核规则：159 条

## 莱塔尼亚权杖（`rogue_1_relic_c03`）

- 主题：`rogue_1`
- 描述：所有敌方单位的攻击力、防御力、生命+30%，且每进入一个新节点后，失去1目标生命（最多降至1）
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.3；operator.def_pct add 0.3；enemy.hp_pct add 0.3；enemy.atk_pct add 0.3；enemy.def_pct add 0.3
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 高卢长袍（`rogue_1_relic_c04`）

- 主题：`rogue_1`
- 描述：所有敌方单位的攻击力、防御力、生命+25%，且招募4星及以上干员时希望消耗+1
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.25；operator.def_pct add 0.25；enemy.hp_pct add 0.25；enemy.atk_pct add 0.25；enemy.def_pct add 0.25
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 酒神的印记（`rogue_1_relic_c06`）

- 主题：`rogue_1`
- 描述：所有敌方单位的攻击力、防御力、生命+30%，且可同时部署人数-2
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.3；operator.def_pct add 0.3；enemy.hp_pct add 0.3；enemy.atk_pct add 0.3；enemy.def_pct add 0.3
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 乌萨斯弯刀（重铸）（`rogue_1_relic_c07`）

- 主题：`rogue_1`
- 描述：所有敌方单位的攻击力、防御力、生命+35%，每进入新的一层额外+10%，完成紧急作战时-5%（最低35%）
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.35；operator.def_pct add 0.35；enemy.hp_pct add 0.35；enemy.atk_pct add 0.35；enemy.def_pct add 0.35
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 莱塔尼亚权杖（重铸）（`rogue_1_relic_c09`）

- 主题：`rogue_1`
- 描述：所有敌方单位的攻击力、防御力、生命+35%，进入节点时目标生命-1（最低降至1），关卡生命低于3时我方部署费用+2，技力回复速度-20%
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.35；operator.def_pct add 0.35；enemy.hp_pct add 0.35；enemy.atk_pct add 0.35；enemy.def_pct add 0.35
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 高卢长袍（重铸）（`rogue_1_relic_c10`）

- 主题：`rogue_1`
- 描述：所有敌方单位的攻击力、防御力、生命+30%，在奇数层招募4星以上干员时希望消耗+2，偶数层晋升干员希望消耗+2
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.3；operator.def_pct add 0.3；enemy.hp_pct add 0.3；enemy.atk_pct add 0.3；enemy.def_pct add 0.3
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 酒神的印记（重铸）（`rogue_1_relic_c12`）

- 主题：`rogue_1`
- 描述：所有敌方单位的攻击力、防御力、生命+35%，可同时部署人数-3，每次进入幕间余兴时可同时部署人数+2
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.35；operator.def_pct add 0.35；enemy.hp_pct add 0.35；enemy.atk_pct add 0.35；enemy.def_pct add 0.35
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## “断剑”（`rogue_1_relic_m05`）

- 主题：`rogue_1`
- 描述：所有干员的生命-30%，但再部署时间-50%
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add -0.3
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## “噤声”（`rogue_1_relic_n15`）

- 主题：`rogue_1`
- 描述：所有我方干员技能未开启时60秒内攻击力逐渐提升至最高+60%，每次技能结束时失去该加成
- 风险：conditional wording without structured conditions
- 当前规则：operator.atk_pct add 0.6
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 近卫军帽（`rogue_1_relic_sp02`）

- 主题：`rogue_1`
- 描述：在一局战斗中，所有干员每部署过一次就生命+25%
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.25
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 深蓝之树（`rogue_2_relic_curse_10`）

- 主题：`rogue_2`
- 描述：所有敌人攻击速度+15；每次作战若未损失目标生命，战斗结束后灯火+15
- 风险：conditional wording without structured conditions
- 当前规则：enemy.aspd add 15.0
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 黑色郁金香（`rogue_2_relic_fight_107`）

- 主题：`rogue_2`
- 描述：所有我方干员技能未开启时60秒内攻击力逐渐提升至最高+60%，每次技能结束时失去该加成
- 风险：conditional wording without structured conditions
- 当前规则：operator.atk_pct add 0.6
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 遗落之帜（`rogue_2_relic_fight_128`）

- 主题：`rogue_2`
- 描述：每次战斗会随机一个可部署位置，该位置上的我方单位攻击力+50%，攻击速度+50
- 风险：conditional wording without structured conditions
- 当前规则：operator.atk_pct add 0.5；operator.aspd add 50.0
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 古乔治营养原浆（`rogue_2_relic_fight_140`）

- 主题：`rogue_2`
- 描述：干员生命值越高，攻击力越高，100%生命值时达到最大可提升攻击力（+30%）
- 风险：conditional wording without structured conditions
- 当前规则：operator.atk_pct add 0.3
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 紧急活性剂（`rogue_2_relic_fight_141`）

- 主题：`rogue_2`
- 描述：干员生命值越低，攻击速度越快，30%生命值时达到最大可提升攻击速度（+60）
- 风险：conditional wording without structured conditions
- 当前规则：operator.aspd add 60.0
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 蓝卡坞安全衣（`rogue_2_relic_fight_142`）

- 主题：`rogue_2`
- 描述：每拥有一个遭诅古物，所有友方单位防御力+25%，法术抗性+10
- 风险：conditional wording without structured conditions
- 当前规则：operator.def_pct add 0.25
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 《刀光剑影》（`rogue_2_relic_fight_143`）

- 主题：`rogue_2`
- 描述：每拥有一个遭诅古物，所有友方单位攻击速度+35
- 风险：conditional wording without structured conditions
- 当前规则：operator.aspd add 35.0
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## “分浪”（`rogue_2_relic_fight_41`）

- 主题：`rogue_2`
- 描述：所有干员的生命-25%，但再部署时间-50%
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add -0.25
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 教堂救济餐券（`rogue_2_relic_grace_10`）

- 主题：`rogue_2`
- 描述：可同时部署人数+2，所有我方单位的生命值+6%
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.06
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 地形图（`rogue_2_relic_grace_7`）

- 主题：`rogue_2`
- 描述：可同时部署人数+1，所有我方单位的防御力+4%
- 风险：conditional wording without structured conditions
- 当前规则：operator.def_pct add 0.04
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 神音海螺（`rogue_2_relic_grace_8`）

- 主题：`rogue_2`
- 描述：可同时部署人数+1，所有我方单位的生命值+4%
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.04
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## “决心”（`rogue_2_relic_grace_88`）

- 主题：`rogue_2`
- 描述：所有我方干员阻挡数+2，防御力和生命+120%，法术抗性+20，让探索走向不同的结局
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 1.2；operator.def_pct add 1.2
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 林间夜话（`rogue_2_relic_grace_9`）

- 主题：`rogue_2`
- 描述：可同时部署人数+2，所有我方单位的防御力+6%
- 风险：conditional wording without structured conditions
- 当前规则：operator.def_pct add 0.06
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 断杖-和声（`rogue_3_relic_book_7`）

- 主题：`rogue_3`
- 描述：场上每有一名术师干员，所有敌人受到的法术伤害+12%（最多叠加8次）
- 风险：conditional wording without structured conditions
- 当前规则：operator.arts_damage_pct multiply 0.12
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 安玛的爱（`rogue_3_relic_explore_6`）

- 主题：`rogue_3`
- 描述：所有我方单位的生命、攻击力、防御力+1%；有时会发挥奇妙的效果
- 风险：conditional wording without structured conditions
- 当前规则：operator.atk_pct add 0.01；operator.hp_pct add 0.01；operator.def_pct add 0.01
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 万星园之辉（`rogue_3_relic_fight_24`）

- 主题：`rogue_3`
- 描述：敌人进入和解除浮空、失重状态时，受到2000点法术伤害，并在10秒内受到的伤害+30%
- 风险：conditional wording without structured conditions
- 当前规则：operator.damage_pct multiply 0.3
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## “永夜的窥视”（`rogue_3_relic_fight_6`）

- 主题：`rogue_3`
- 描述：所有干员的攻击力+25%，攻击速度+25，但每秒流失25生命值
- 风险：conditional wording without structured conditions
- 当前规则：operator.atk_pct add 0.25；operator.aspd add 25.0
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## “枯木的回声”（`rogue_3_relic_fight_7`）

- 主题：`rogue_3`
- 描述：所有干员每秒恢复50生命值，但最大生命-25%
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add -0.25
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 黑色郁金香（`rogue_3_relic_legacy_156`）

- 主题：`rogue_3`
- 描述：所有我方干员技能未开启时60秒内攻击力逐渐提升至最高+60%，每次技能结束时失去该加成
- 风险：conditional wording without structured conditions
- 当前规则：operator.atk_pct add 0.6
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 地形图（`rogue_3_relic_legacy_16`）

- 主题：`rogue_3`
- 描述：可同时部署人数+1，所有我方单位的防御力+4%
- 风险：conditional wording without structured conditions
- 当前规则：operator.def_pct add 0.04
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 地形图-α（`rogue_3_relic_legacy_16_a`）

- 主题：`rogue_3`
- 描述：可同时部署人数+1，所有我方单位的防御力+5%
- 风险：conditional wording without structured conditions
- 当前规则：operator.def_pct add 0.05
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 地形图-β（`rogue_3_relic_legacy_16_b`）

- 主题：`rogue_3`
- 描述：可同时部署人数+1，所有我方单位的防御力+6%
- 风险：conditional wording without structured conditions
- 当前规则：operator.def_pct add 0.06
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 神音海螺（`rogue_3_relic_legacy_17`）

- 主题：`rogue_3`
- 描述：可同时部署人数+1，所有我方单位的生命值+4%
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.04
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 神音海螺-α（`rogue_3_relic_legacy_17_a`）

- 主题：`rogue_3`
- 描述：可同时部署人数+1，所有我方单位的生命值+5%
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.05
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 神音海螺-β（`rogue_3_relic_legacy_17_b`）

- 主题：`rogue_3`
- 描述：可同时部署人数+1，所有我方单位的生命值+6%
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.06
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 林间夜话（`rogue_3_relic_legacy_18`）

- 主题：`rogue_3`
- 描述：可同时部署人数+2，所有我方单位的防御力+6%
- 风险：conditional wording without structured conditions
- 当前规则：operator.def_pct add 0.06
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 林间夜话-α（`rogue_3_relic_legacy_18_a`）

- 主题：`rogue_3`
- 描述：可同时部署人数+2，所有我方单位的防御力+7%
- 风险：conditional wording without structured conditions
- 当前规则：operator.def_pct add 0.07
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 林间夜话-β（`rogue_3_relic_legacy_18_b`）

- 主题：`rogue_3`
- 描述：可同时部署人数+2，所有我方单位的防御力+8%
- 风险：conditional wording without structured conditions
- 当前规则：operator.def_pct add 0.08
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 教堂救济餐券（`rogue_3_relic_legacy_19`）

- 主题：`rogue_3`
- 描述：可同时部署人数+2，所有我方单位的生命值+6%
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.06
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 教堂救济餐券-α（`rogue_3_relic_legacy_19_a`）

- 主题：`rogue_3`
- 描述：可同时部署人数+2，所有我方单位的生命值+7%
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.07
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 教堂救济餐券-β（`rogue_3_relic_legacy_19_b`）

- 主题：`rogue_3`
- 描述：可同时部署人数+2，所有我方单位的生命值+8%
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.08
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 琥珀伤痕（`rogue_3_relic_res_12`）

- 主题：`rogue_3`
- 描述：抗干扰指数可以超出上限，且每超出1点使所有我方单位的生命值+8%，攻击力+8%
- 风险：conditional wording without structured conditions
- 当前规则：operator.atk_pct add 0.08；operator.hp_pct add 0.08
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 断杖-波纹（`rogue_4_relic_book_3`）

- 主题：`rogue_4`
- 描述：场上每有一名术师干员，所有敌人受到的法术伤害+12%（最多叠加8层）
- 风险：conditional wording without structured conditions
- 当前规则：operator.arts_damage_pct multiply 0.12
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 丝契之谜（`rogue_4_relic_encounter_8`）

- 主题：`rogue_4`
- 描述：干员周围8格存在其他干员时持续受到伤害，干员周围8格不存在其他干员时攻击速度+50，仅在诡谲断章中生效
- 风险：conditional wording without structured conditions
- 当前规则：operator.aspd add 50.0
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 死仇时代的恨意（`rogue_4_relic_explore_3`）

- 主题：`rogue_4`
- 描述：所有友方单位和敌人攻击力+20%，刷新节点时更容易出现紧急作战，在不期而遇中会发挥奇妙的效果
- 风险：conditional wording without structured conditions
- 当前规则：enemy.atk_pct add 0.2
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 束灵骨（`rogue_4_relic_fight_21`）

- 主题：`rogue_4`
- 描述：每携带一缕思绪，所有干员攻击力+3%
- 风险：conditional wording without structured conditions
- 当前规则：operator.atk_pct add 0.03
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 生命熔炉之薪（`rogue_4_relic_fight_22`）

- 主题：`rogue_4`
- 描述：每携带一缕思绪，所有干员攻击力+5%
- 风险：conditional wording without structured conditions
- 当前规则：operator.atk_pct add 0.05
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 青涩眷恋（`rogue_4_relic_fight_25`）

- 主题：`rogue_4`
- 描述：每携带一缕思绪，所有干员最大生命值+3%，防御力+3%
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.03；operator.def_pct add 0.03
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 咒仪溯兽（`rogue_4_relic_fight_26`）

- 主题：`rogue_4`
- 描述：所有干员攻速+5，每次作战结束后消耗一个灵感，使所有干员攻速+5（可叠加10次）
- 风险：conditional wording without structured conditions
- 当前规则：operator.aspd add 10.0
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 黑色郁金香（`rogue_4_relic_legacy_145`）

- 主题：`rogue_4`
- 描述：所有我方干员技能未开启时60秒内攻击力逐渐提升至最高+60%，每次技能结束时失去该加成
- 风险：conditional wording without structured conditions
- 当前规则：operator.atk_pct add 0.6
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 地形图（`rogue_4_relic_legacy_15`）

- 主题：`rogue_4`
- 描述：可同时部署人数+1，所有我方单位的防御力+4%
- 风险：conditional wording without structured conditions
- 当前规则：operator.def_pct add 0.04
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 地形图-α（`rogue_4_relic_legacy_15_a`）

- 主题：`rogue_4`
- 描述：可同时部署人数+1，所有我方单位的防御力+5%
- 风险：conditional wording without structured conditions
- 当前规则：operator.def_pct add 0.05
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 地形图-β（`rogue_4_relic_legacy_15_b`）

- 主题：`rogue_4`
- 描述：可同时部署人数+1，所有我方单位的防御力+6%
- 风险：conditional wording without structured conditions
- 当前规则：operator.def_pct add 0.06
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 地形图-γ（`rogue_4_relic_legacy_15_c`）

- 主题：`rogue_4`
- 描述：可同时部署人数+1，所有我方单位的防御力+8%
- 风险：conditional wording without structured conditions
- 当前规则：operator.def_pct add 0.08
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 神音海螺（`rogue_4_relic_legacy_16`）

- 主题：`rogue_4`
- 描述：可同时部署人数+1，所有我方单位的生命值+4%
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.04
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 神音海螺-α（`rogue_4_relic_legacy_16_a`）

- 主题：`rogue_4`
- 描述：可同时部署人数+1，所有我方单位的生命值+5%
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.05
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 神音海螺-β（`rogue_4_relic_legacy_16_b`）

- 主题：`rogue_4`
- 描述：可同时部署人数+1，所有我方单位的生命值+6%
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.06
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 神音海螺-γ（`rogue_4_relic_legacy_16_c`）

- 主题：`rogue_4`
- 描述：可同时部署人数+1，所有我方单位的生命值+8%
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.08
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 林间夜话（`rogue_4_relic_legacy_17`）

- 主题：`rogue_4`
- 描述：可同时部署人数+2，所有我方单位的防御力+6%
- 风险：conditional wording without structured conditions
- 当前规则：operator.def_pct add 0.06
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 林间夜话-α（`rogue_4_relic_legacy_17_a`）

- 主题：`rogue_4`
- 描述：可同时部署人数+2，所有我方单位的防御力+7%
- 风险：conditional wording without structured conditions
- 当前规则：operator.def_pct add 0.07
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 林间夜话-β（`rogue_4_relic_legacy_17_b`）

- 主题：`rogue_4`
- 描述：可同时部署人数+2，所有我方单位的防御力+8%
- 风险：conditional wording without structured conditions
- 当前规则：operator.def_pct add 0.08
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 林间夜话-γ（`rogue_4_relic_legacy_17_c`）

- 主题：`rogue_4`
- 描述：可同时部署人数+2，所有我方单位的防御力+10%
- 风险：conditional wording without structured conditions
- 当前规则：operator.def_pct add 0.1
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 教堂救济餐券（`rogue_4_relic_legacy_18`）

- 主题：`rogue_4`
- 描述：可同时部署人数+2，所有我方单位的生命值+6%
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.06
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 古乔治营养原浆（`rogue_4_relic_legacy_181`）

- 主题：`rogue_4`
- 描述：干员生命值越高，攻击力越高，100%生命值时达到最大可提升攻击力（+30%）
- 风险：conditional wording without structured conditions
- 当前规则：operator.atk_pct add 0.3
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 紧急活性剂（`rogue_4_relic_legacy_182`）

- 主题：`rogue_4`
- 描述：干员生命值越低，攻击速度越快，30%生命值时达到最大可提升攻击速度（+60）
- 风险：conditional wording without structured conditions
- 当前规则：operator.aspd add 60.0
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 教堂救济餐券-α（`rogue_4_relic_legacy_18_a`）

- 主题：`rogue_4`
- 描述：可同时部署人数+2，所有我方单位的生命值+7%
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.07
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 教堂救济餐券-β（`rogue_4_relic_legacy_18_b`）

- 主题：`rogue_4`
- 描述：可同时部署人数+2，所有我方单位的生命值+8%
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.08
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 教堂救济餐券-γ（`rogue_4_relic_legacy_18_c`）

- 主题：`rogue_4`
- 描述：可同时部署人数+2，所有我方单位的生命值+10%
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.1
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 四方绘料（`rogue_5_relic_cardg_1`）

- 主题：`rogue_5`
- 描述：每场战斗仅一次，已部署4名干员时，下一名部署的干员获得生命值+50%，防御力+50%，阻挡数+5
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.5；operator.def_pct add 0.5
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 四时丹青毫（`rogue_5_relic_cardg_2`）

- 主题：`rogue_5`
- 描述：每场战斗仅一次，已部署4名干员时，下一名部署的干员获得抵抗，攻击力+50%，受到的元素损伤降低50%
- 风险：conditional wording without structured conditions
- 当前规则：operator.atk_pct add 0.5
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 艺影（`rogue_5_relic_cardg_5`）

- 主题：`rogue_5`
- 描述：进入战斗时，待部署区最左侧的干员初始技力+10，攻击速度+30，攻击力+30%
- 风险：conditional wording without structured conditions
- 当前规则：operator.atk_pct add 0.3；operator.aspd add 30.0
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 商影（`rogue_5_relic_cardg_6`）

- 主题：`rogue_5`
- 描述：进入战斗时，待部署区最右侧的干员阻挡数+2，防御力+50%，最大生命值+50%，部署后返回50%的部署费用
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.5；operator.def_pct add 0.5
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 家常小炒（`rogue_5_relic_explore_3`）

- 主题：`rogue_5`
- 描述：所有干员的生命值+20%，攻击力+20%；每通过一场岁兽残识中的战斗，效果额外提升10%
- 风险：conditional wording without structured conditions
- 当前规则：operator.atk_pct add 0.2；operator.hp_pct add 0.2
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 封神令（`rogue_5_relic_fight_1`）

- 主题：`rogue_5`
- 描述：干员部署在侵入点周围8格时，攻击力+100%
- 风险：conditional wording without structured conditions
- 当前规则：operator.atk_pct add 1.0
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 无封长盒（`rogue_5_relic_final_5`）

- 主题：`rogue_5`
- 描述：领袖与精英敌人防御力+30%，攻击速度+20，关卡结束时每有一个仍在场的雕伥，失去1目标生命值（不会低于1），在先行一步中有奇妙的作用
- 风险：conditional wording without structured conditions
- 当前规则：operator.aspd add 20.0；enemy.def_pct add 0.3
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 地形图（`rogue_5_relic_legacy_33`）

- 主题：`rogue_5`
- 描述：可同时部署人数+1，所有我方单位的防御力+4%
- 风险：conditional wording without structured conditions
- 当前规则：operator.def_pct add 0.04
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 地形图-α（`rogue_5_relic_legacy_33_a`）

- 主题：`rogue_5`
- 描述：可同时部署人数+1，所有我方单位的防御力+5%
- 风险：conditional wording without structured conditions
- 当前规则：operator.def_pct add 0.05
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 地形图-β（`rogue_5_relic_legacy_33_b`）

- 主题：`rogue_5`
- 描述：可同时部署人数+1，所有我方单位的防御力+6%
- 风险：conditional wording without structured conditions
- 当前规则：operator.def_pct add 0.06
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 地形图-γ（`rogue_5_relic_legacy_33_c`）

- 主题：`rogue_5`
- 描述：可同时部署人数+1，所有我方单位的防御力+8%
- 风险：conditional wording without structured conditions
- 当前规则：operator.def_pct add 0.08
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 神音海螺（`rogue_5_relic_legacy_34`）

- 主题：`rogue_5`
- 描述：可同时部署人数+1，所有我方单位的生命值+4%
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.04
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 神音海螺-α（`rogue_5_relic_legacy_34_a`）

- 主题：`rogue_5`
- 描述：可同时部署人数+1，所有我方单位的生命值+5%
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.05
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 神音海螺-β（`rogue_5_relic_legacy_34_b`）

- 主题：`rogue_5`
- 描述：可同时部署人数+1，所有我方单位的生命值+6%
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.06
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 神音海螺-γ（`rogue_5_relic_legacy_34_c`）

- 主题：`rogue_5`
- 描述：可同时部署人数+1，所有我方单位的生命值+8%
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.08
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 林间夜话（`rogue_5_relic_legacy_35`）

- 主题：`rogue_5`
- 描述：可同时部署人数+2，所有我方单位的防御力+6%
- 风险：conditional wording without structured conditions
- 当前规则：operator.def_pct add 0.06
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 林间夜话-α（`rogue_5_relic_legacy_35_a`）

- 主题：`rogue_5`
- 描述：可同时部署人数+2，所有我方单位的防御力+7%
- 风险：conditional wording without structured conditions
- 当前规则：operator.def_pct add 0.07
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 林间夜话-β（`rogue_5_relic_legacy_35_b`）

- 主题：`rogue_5`
- 描述：可同时部署人数+2，所有我方单位的防御力+8%
- 风险：conditional wording without structured conditions
- 当前规则：operator.def_pct add 0.08
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 林间夜话-γ（`rogue_5_relic_legacy_35_c`）

- 主题：`rogue_5`
- 描述：可同时部署人数+2，所有我方单位的防御力+10%
- 风险：conditional wording without structured conditions
- 当前规则：operator.def_pct add 0.1
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 教堂救济餐券（`rogue_5_relic_legacy_36`）

- 主题：`rogue_5`
- 描述：可同时部署人数+2，所有我方单位的生命值+6%
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.06
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 教堂救济餐券-α（`rogue_5_relic_legacy_36_a`）

- 主题：`rogue_5`
- 描述：可同时部署人数+2，所有我方单位的生命值+7%
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.07
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 教堂救济餐券-β（`rogue_5_relic_legacy_36_b`）

- 主题：`rogue_5`
- 描述：可同时部署人数+2，所有我方单位的生命值+8%
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.08
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 教堂救济餐券-γ（`rogue_5_relic_legacy_36_c`）

- 主题：`rogue_5`
- 描述：可同时部署人数+2，所有我方单位的生命值+10%
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.1
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 断杖-波纹（`rogue_5_relic_legacy_47`）

- 主题：`rogue_5`
- 描述：场上每有一名术师干员，所有敌人受到的法术伤害+12%（最多叠加8层）
- 风险：conditional wording without structured conditions
- 当前规则：operator.arts_damage_pct multiply 0.12
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 万星园之辉（`rogue_5_relic_legacy_73`）

- 主题：`rogue_5`
- 描述：敌人进入和解除浮空、失重状态时，受到2000点法术伤害，并在10秒内受到的伤害+30%
- 风险：conditional wording without structured conditions
- 当前规则：operator.damage_pct multiply 0.3
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 黑色郁金香（`rogue_5_relic_return_18`）

- 主题：`rogue_5`
- 描述：所有我方干员技能未开启时60秒内攻击力逐渐提升至最高+60%，每次技能结束时失去该加成
- 风险：conditional wording without structured conditions
- 当前规则：operator.atk_pct add 0.6
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 紧急活性剂（`rogue_5_relic_return_19`）

- 主题：`rogue_5`
- 描述：干员生命值越低，攻击速度越快，30%生命值时达到最大可提升攻击速度（+60）
- 风险：conditional wording without structured conditions
- 当前规则：operator.aspd add 60.0
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 古乔治营养原浆（`rogue_5_relic_return_20`）

- 主题：`rogue_5`
- 描述：干员生命值越高，攻击力越高，100%生命值时达到最大可提升攻击力（+30%）
- 风险：conditional wording without structured conditions
- 当前规则：operator.atk_pct add 0.3
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 奔兽战车（`rogue_5_relic_richg_4`）

- 主题：`rogue_5`
- 描述：部署费用上限+30，部署费用为99及以上时，所有单位生命值+50%，阻挡数+1
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.5
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 酿山河（`rogue_5_relic_speg_4`）

- 主题：`rogue_5`
- 描述：钱盒内每存在一枚花钱，所有干员获得+10%攻击力，+20%生命值
- 风险：conditional wording without structured conditions
- 当前规则：operator.atk_pct add 0.2
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 仇名录（`rogue_6_relic_artifact_7`）

- 主题：`rogue_6`
- 描述：我方干员的攻击力+2%，每击倒一名敌人永久额外+0.2%（最高+200%）
- 风险：conditional wording without structured conditions
- 当前规则：operator.atk_pct add 0.02
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 热辣可可（`rogue_6_relic_fight_14`）

- 主题：`rogue_6`
- 描述：干员生命值越低，攻击力越高，30%生命值时达到最大可提升攻击力（+150%）
- 风险：conditional wording without structured conditions
- 当前规则：operator.atk_pct add 1.5
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 紧急活性剂（`rogue_6_relic_legacy_102`）

- 主题：`rogue_6`
- 描述：干员生命值越低，攻击速度越快，30%生命值时达到最大可提升攻击速度（+100）
- 风险：conditional wording without structured conditions
- 当前规则：operator.aspd add 100.0
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 地形图（`rogue_6_relic_legacy_28`）

- 主题：`rogue_6`
- 描述：可同时部署人数+1，所有我方单位的防御力+4%
- 风险：conditional wording without structured conditions
- 当前规则：operator.def_pct add 0.04
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 地形图-α（`rogue_6_relic_legacy_28_a`）

- 主题：`rogue_6`
- 描述：可同时部署人数+1，所有我方单位的防御力+5%
- 风险：conditional wording without structured conditions
- 当前规则：operator.def_pct add 0.05
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 地形图-β（`rogue_6_relic_legacy_28_b`）

- 主题：`rogue_6`
- 描述：可同时部署人数+1，所有我方单位的防御力+6%
- 风险：conditional wording without structured conditions
- 当前规则：operator.def_pct add 0.06
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 地形图-γ（`rogue_6_relic_legacy_28_c`）

- 主题：`rogue_6`
- 描述：可同时部署人数+1，所有我方单位的防御力+8%
- 风险：conditional wording without structured conditions
- 当前规则：operator.def_pct add 0.08
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 神音海螺（`rogue_6_relic_legacy_29`）

- 主题：`rogue_6`
- 描述：可同时部署人数+1，所有我方单位的生命值+4%
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.04
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 神音海螺-α（`rogue_6_relic_legacy_29_a`）

- 主题：`rogue_6`
- 描述：可同时部署人数+1，所有我方单位的生命值+5%
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.05
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 神音海螺-β（`rogue_6_relic_legacy_29_b`）

- 主题：`rogue_6`
- 描述：可同时部署人数+1，所有我方单位的生命值+6%
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.06
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 神音海螺-γ（`rogue_6_relic_legacy_29_c`）

- 主题：`rogue_6`
- 描述：可同时部署人数+1，所有我方单位的生命值+8%
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.08
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 林间夜话（`rogue_6_relic_legacy_30`）

- 主题：`rogue_6`
- 描述：可同时部署人数+2，所有我方单位的防御力+6%
- 风险：conditional wording without structured conditions
- 当前规则：operator.def_pct add 0.06
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 林间夜话-α（`rogue_6_relic_legacy_30_a`）

- 主题：`rogue_6`
- 描述：可同时部署人数+2，所有我方单位的防御力+7%
- 风险：conditional wording without structured conditions
- 当前规则：operator.def_pct add 0.07
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 林间夜话-β（`rogue_6_relic_legacy_30_b`）

- 主题：`rogue_6`
- 描述：可同时部署人数+2，所有我方单位的防御力+8%
- 风险：conditional wording without structured conditions
- 当前规则：operator.def_pct add 0.08
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 林间夜话-γ（`rogue_6_relic_legacy_30_c`）

- 主题：`rogue_6`
- 描述：可同时部署人数+2，所有我方单位的防御力+10%
- 风险：conditional wording without structured conditions
- 当前规则：operator.def_pct add 0.1
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 教堂救济餐券（`rogue_6_relic_legacy_31`）

- 主题：`rogue_6`
- 描述：可同时部署人数+2，所有我方单位的生命值+6%
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.06
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 教堂救济餐券-α（`rogue_6_relic_legacy_31_a`）

- 主题：`rogue_6`
- 描述：可同时部署人数+2，所有我方单位的生命值+7%
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.07
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 教堂救济餐券-β（`rogue_6_relic_legacy_31_b`）

- 主题：`rogue_6`
- 描述：可同时部署人数+2，所有我方单位的生命值+8%
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.08
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 教堂救济餐券-γ（`rogue_6_relic_legacy_31_c`）

- 主题：`rogue_6`
- 描述：可同时部署人数+2，所有我方单位的生命值+10%
- 风险：conditional wording without structured conditions
- 当前规则：operator.hp_pct add 0.1
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。

## 襁褓九头蛇（`rogue_6_start_4`）

- 主题：`rogue_6`
- 描述：所有敌人的攻击和生命+30%，每进入新区域时我方攻击力和生命+10%
- 风险：conditional wording without structured conditions
- 当前规则：operator.atk_pct add 0.1；operator.hp_pct add 0.1
- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。
