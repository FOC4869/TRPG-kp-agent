import type { AttributeKey, InvestigatorDetail, InvestigatorSkill } from '../types/investigators'

// UI-only dummy records. Authored independently, never imported from backend assets.
// These values and portraits are not an authoritative transcription of role cards.
interface PreviewSeed {
  id: string
  name: string
  displayName?: string
  occupation: string
  age: number
  overview: string
  skills: [string, number][]
}

const seeds: PreviewSeed[] = [
  { id: 'stanley', name: '史丹利·艾斯', occupation: '拳击手', age: 25, overview: '乐于冒险的行动派，遇到难题时习惯先迈出第一步。比起纸上的推论，他更相信亲自观察。', skills: [['斗殴', 80], ['闪避', 55], ['攀爬', 50], ['考古学', 45]] },
  { id: 'jessica', name: '杰西卡·布鲁克斯', occupation: '作家', age: 52, overview: '对陌生人的故事怀有浓厚兴趣，习惯把细节记在笔记本里。她相信，一段不起眼的对话也可能藏着关键。', skills: [['文学', 70], ['说服', 60], ['历史', 50], ['图书馆使用', 45]] },
  { id: 'melissa', name: '梅丽莎·德弗丽丝', occupation: '科学家', age: 31, overview: '冷静而讲求证据，喜欢从现象中寻找可以验证的解释。她会仔细检查每一处值得怀疑的痕迹。', skills: [['生物学', 65], ['图书馆使用', 55], ['侦查', 50], ['化学', 45]] },
  { id: 'jacob', name: '雅各布·吉普森', occupation: '门卫', age: 36, overview: '安静、务实，擅长留意被旁人忽略的事物。他熟悉各种工具，也愿意耐心处理复杂的机械问题。', skills: [['机械维修', 75], ['电气维修', 55], ['潜行', 50], ['斗殴', 45]] },
  { id: 'john_lucas', name: '约翰·卢卡斯医生', displayName: '约翰·卢卡斯', occupation: '内科医生', age: 37, overview: '做事谨慎，习惯先检查情况再下判断。面对紧急事件时，他努力保持镇定并照料身边的人。', skills: [['医学', 75], ['急救', 70], ['生物学', 60], ['心理学', 40]] },
  { id: 'david', name: '大卫“不可思议的克雷格”威尔考克斯', displayName: '大卫·威尔考克斯', occupation: '舞台魔术师', age: 36, overview: '外向而健谈，对难以解释的现象充满好奇。熟悉舞台上的障眼法，也知道人们的注意力有多容易被转移。', skills: [['魔术', 75], ['妙手', 65], ['话术', 55], ['锁匠', 45]] },
  { id: 'chris', name: '克丽斯·帕克', occupation: '地质学教授', age: 39, overview: '亲切开朗，富有冒险精神。工作之外，她是一位热衷探索自然洞穴的爱好者。', skills: [['地质学', 80], ['攀爬', 60], ['跳跃', 60], ['机械维修', 45]] },
  { id: 'stephen', name: '史蒂芬·谢泼洛夫斯基神父', displayName: '史蒂芬神父', occupation: '天主教神父', age: 25, overview: '温和而有耐心，愿意听取他人的困扰。信念让他在不安的环境中继续前行，也让他更在意同行者的处境。', skills: [['拉丁语', 70], ['说服', 55], ['历史', 50], ['聆听', 45]] },
  { id: 'geraldine', name: '杰拉尔丁“格里”桑希尔', displayName: '格里·桑希尔', occupation: '记者', age: 32, overview: '敏锐、好奇，喜欢追问没有人愿意回答的问题。随身笔记里充满零碎线索，等待她把它们连成一个故事。', skills: [['写作', 70], ['心理学', 60], ['话术', 55], ['图书馆使用', 50]] },
  { id: 'maximilian', name: '麦克斯米兰·赫斯特', occupation: '心理学家', age: 26, overview: '善于倾听，也常常反省自己的判断。他对那些超出日常经验的见闻抱有兴趣，愿意花时间寻找其中的联系。', skills: [['神秘学', 65], ['心理学', 60], ['话术', 50], ['摄影', 45]] },
]

const attributeKeys: AttributeKey[] = ['STR', 'CON', 'SIZ', 'DEX', 'APP', 'INT', 'POW', 'EDU']

export const previewInvestigators: InvestigatorDetail[] = seeds.map((seed, index) => {
  const attributes = Object.fromEntries(attributeKeys.map((key, position) => [key, 45 + ((index + position * 2) % 9) * 5])) as Record<AttributeKey, number>
  if (seed.id === 'chris') Object.assign(attributes, { STR: 60, CON: 60, SIZ: 45, DEX: 75, APP: 55, INT: 70, POW: 55, EDU: 90 })
  const skills: InvestigatorSkill[] = seed.skills.map(([name, value]) => ({ name, value, highlighted: true }))
  return {
    ...seed,
    displayName: seed.displayName ?? seed.name,
    portrait: { url: '/images/investigator-previews.webp', sprite: { column: index % 5, row: Math.floor(index / 5), columns: 5, rows: 2 } },
    attributes,
    resources: seed.id === 'chris'
      ? { hp: 10, hpMax: 10, san: 55, mp: 11, mpMax: 11, luck: 60 }
      : { hp: 11 + index % 5, hpMax: 11 + index % 5, san: 45 + index % 5 * 5, mp: 10 + index % 4, mpMax: 10 + index % 4, luck: 40 + index % 5 * 5 },
    skills: [...skills, ...[{ name: '聆听', value: 35 }, { name: '导航', value: null }].filter((extra) => !skills.some((skill) => skill.name === extra.name))],
    background: [
      { title: '人物经历', text: seed.overview },
      { title: '思想与信念', text: '相信细致的观察与诚实的交流，愿意追寻尚未得到解答的问题。' },
      { title: '重要之人', text: null },
      { title: '意义非凡之地', text: null },
      { title: '宝贵之物', text: '一本记录旅行见闻的旧笔记。此项为背景描述，不自动加入随身物品。' },
    ],
    equipment: [
      { name: '随身笔记本', quantity: 1, kind: 'carried' },
      { name: '手电筒', quantity: 1, kind: 'carried' },
      { name: '日常用品', quantity: null, kind: 'carried', note: '具体数量尚未提供。' },
      ...(seed.id === 'jessica' ? [{ name: '汽车', quantity: 1, kind: 'owned' as const, note: '拥有资产，不等同于已携带的物品。' }] : []),
    ],
    cash: { amount: 10, currency: 'USD' },
  }
})
