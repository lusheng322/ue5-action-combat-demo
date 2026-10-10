# Slash —— 3D 动作战斗 Demo（Unreal Engine 5.6 / C++）

一个用 **UE5 C++** 实现的第三人称动作战斗项目：角色状态机、武器命中判定、敌人 AI、属性系统、UMG HUD。
本项目按"**代码仓库**"方式公开：**只包含 C++ 源码与配置**，第三方美术资源（约 13.8 GB）未包含（见下方说明）。

> 引擎版本：**Unreal Engine 5.6**（`Slash.uproject`）

---

## 一、仓库包含 / 不包含什么

| 目录 | 是否包含 | 说明 |
|---|---|---|
| `Source/Slash/` | ✅ | 全部 C++ 源码（Private / Public，2045 行） |
| `Config/` | ✅ | DefaultEngine / DefaultGame / DefaultInput 等配置 |
| `Slash.uproject` | ✅ | 项目描述文件 |
| `Content/` | ❌ | 第三方与教程美术资源共 13.47 GB（4983 个文件），含 Marketplace 资源，**不入库** |
| `Binaries/ Intermediate/ Saved/ .vs/` | ❌ | 编译产物与编辑器缓存 |

> 因此：**克隆本仓库后可以直接阅读/评审全部 C++ 代码**；若要运行完整工程，需自备对应的美术资源包。

---

## 二、代码结构

```
Source/Slash/
├── Public/ / Private/
│   ├── Character/
│   │   ├── BaseCharacter.h/.cpp        # 玩家与敌人的公共基类（模板方法）
│   │   ├── SlashCharacter.h/.cpp       # 玩家：输入、装备、攻击、闪避、HUD
│   │   ├── SlashAnimInstance.h/.cpp    # 动画数据桥（把角色状态喂给动画蓝图）
│   │   └── CharacterType.h             # 枚举（角色状态 / 动作状态 / 敌人状态 / 死亡姿势）
│   ├── Components/
│   │   └── AttributeComponent.h/.cpp   # 属性组件：血量 / 耐力 / 金币 / 魂
│   ├── Actors/
│   │   ├── Item.h/.cpp                 # 可拾取物基类
│   │   ├── Weapons/Weapon.h/.cpp        # 武器：碰撞盒开关、BoxTrace 命中判定、伤害与表现
│   │   ├── Soul.h/.cpp                  # 魂（掉落物）
│   │   └── Treasures/Treasure.h/.cpp    # 宝藏
│   ├── Breakable/BreakableActor.h/.cpp  # 可破坏物（实现 IHitInterface）
│   ├── Enemy/Enemy.h/.cpp               # 敌人：巡逻/追击/攻击状态机、感知、掉落
│   ├── Interface/
│   │   ├── HitInterface.h/.cpp          # 命中接口（被武器调用）
│   │   └── PickupInterface.h/.cpp       # 拾取接口
│   └── HUD/                             # SlashHud / SlashOverlay / HealthBar(Component)
```

---

## 三、代码是怎么组织的

- **基类 + 虚函数钩子**：`ABaseCharacter` 里放公共表现（受击方向判定、音效、粒子、蒙太奇播放、武器碰撞开关），`Attack / Die / HandleDamage / CanAttack` 这些留成虚函数给子类覆写；`ASlashCharacter` 和 `AEnemy` 只写各自不一样的部分。
- **命中与拾取走接口**：武器不关心被打击者是什么类，只按 `IHitInterface` 调用并回传命中信息，所以后面加"可破坏物"没有动武器代码。
- **数值收口到组件**：血量 / 耐力 / 金币 / 魂都在 `UAttributeComponent` 里，HUD 和逻辑读同一份数据。

---

## 四、已实现功能

**玩家**
- 输入：`Config/DefaultInput.ini` 里的传统映射（`ActionMappings` / `AxisMappings`）+ `BindAxis` / `BindAction` 绑定，没有使用 Enhanced Input 的 IMC / IA 资产
- 装备状态（未装备 / 单手 / 双手）与动作状态（空闲 / 受击 / 攻击 / 装备中 / 闪避 / 死亡），枚举定义在 `CharacterType.h`
- 普通攻击（随机攻击段）、闪避（消耗耐力）
- 拾取：走过多边形重叠区即可拾取魂与宝藏（走 `IPickupInterface`）
- UMG HUD：血量 / 耐力 / 金币 / 魂

**战斗**
- 武器盒重叠触发 + `BoxTraceSingle` 精确命中判定
- `IgnoreActors` 保证一次挥砍对同一目标只结算一次命中
- 命中信息（ImpactPoint + 攻击者）通过接口回传给受击方
- 受击方向判定：把命中点降到自身 Z 平面 → 点积求夹角 → 叉积定左右 → 映射到 4 段受击动画
- 攻击期间由动画通知（AnimNotify）开关武器碰撞

**敌人**
- 巡逻 / 追击 / 攻击状态机 + `PawnSensingComponent` 视野感知
- 攻击随机延迟与冷却、受击打断、死亡后掉落魂并延时销毁
- 头顶血条（`UWidgetComponent`）

---

## 五、已知问题与后续计划

- 战斗结果缺少"单一数据源"：数值走引擎伤害管线（`TakeDamage`）、表现与死亡走接口（`GetHit`），两条链依赖调用方成对调用 —— 计划统一为单一伤害入口
- 玩家尚无死亡处理与重生流程
- 拾取物与技能生成物未做对象池

---

## 六、开发说明

- 引擎：Unreal Engine 5.6（`MotionWarping`、`ModelingToolsEditorMode` 插件）
- 语言：C++；内容配置与表现层由蓝图承担（C++ 提供基类与可扩展点）
- 项目采用"**C++ 定架构、蓝图做内容**"的分工：所有动画通知点（`AttackEnd / DodgeEnd / SetWeaponCollisionEnabled` 等）都是 `BlueprintCallable`，节奏由动画蓝图掌握
- 本项目参考Stephen Ulibarri的The Ultimate Developer Course教程，代码均经过自身理解且对敌人受击和死亡流程、可破坏物的碎裂、翻滚等地方按自己的需求做了修改
