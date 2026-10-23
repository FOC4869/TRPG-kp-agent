import type { GameAction, GameMessage, GameReply } from '../types/game'

// Independently authored opening UI examples. No imports from the server module pack.
export const openingScene = {
  scene: { name: '文斯考特宅 · 厨房', region: '普罗维登斯 · 学院山', backgroundUrl: '/images/game-preview/winscott-house.webp' },
  npc: { name: '乔什·文斯考特', role: '作家', spriteUrl: '/images/game-preview/josh.png' },
  suggestions: ['询问隧道', '查看地窖入口', '准备探索装备'],
  messages: [
    { id: 'opening-keeper', kind: 'keeper', speaker: '守秘人', text: '乔什从厨房的地窖楼梯旁走来，向你招呼。他显得兴奋而疲惫。箱子与罩布家具之间，还散落着修缮房屋的工具。' },
    { id: 'opening-josh', kind: 'npc', speaker: '乔什·文斯考特', text: '先坐下喝杯咖啡吧。我在地窖里发现了一条隧道……我想，你一定会感兴趣的。' },
  ] satisfies GameMessage[],
}

/** Scripted preview responses, not an intent model or a rules engine. */
export function previewReply(action: GameAction): GameReply {
  const message = (kind: GameMessage['kind'], text: string): GameMessage => ({ id: `${action.requestId}-reply`, kind, speaker: kind === 'npc' ? '乔什·文斯考特' : '守秘人', text })
  if (action.kind === 'check-preview') return {
    messages: [{ ...message('check', '这是一张固定的检定展示样例，没有实际掷骰或改变人物状态。'), check: { skill: '聆听', target: 35, roll: 28, result: '普通成功' } }], facts: [],
  }
  if (/装备|准备|绳|靴|手电/.test(action.text)) return {
    messages: [message('npc', '最好带上结实的靴子、绳子，还有手电筒。今天实在太累了，我们可以明天再出发。当然，时间由你决定。')],
    facts: [{ id: 'preparations', title: '探索前的准备', text: '乔什建议带上靴子、绳索与手电筒。此记录不代表这些物品已经加入背包。' }],
  }
  if (/地窖|入口|检查|观察|查看/.test(action.text)) return {
    messages: [message('keeper', '你望向厨房一侧的地窖入口。乔什放下咖啡杯，向那个方向点了点头。预览暂时停留在会面场景，你可以继续询问他的发现。')], facts: [],
  }
  if (/隧道|发现|询问|问|交谈/.test(action.text)) return {
    messages: [message('npc', '修缮地窖时，我发现砖墙后面还有空间。我清理了一段，里面比排水道宽敞得多。不过究竟通往哪里，我还不清楚。')],
    facts: [{ id: 'tunnel', title: '砖墙后的通道', text: '据乔什所说，地窖砖墙后藏着一条宽敞的通道，其去向尚不明确。' }],
  }
  if (/咖啡|坐下|喝|你好/.test(action.text)) return {
    messages: [message('keeper', '你在还没收拾妥当的屋里坐下。乔什为你倒了咖啡，迫不及待地想聊起地窖里的发现。')], facts: [],
  }
  return { messages: [message('keeper', '已记录你的行动。这是开场界面预览，还不能完整裁定自由行动；可以试着询问隧道、查看地窖入口，或讨论探索装备。')], facts: [] }
}
