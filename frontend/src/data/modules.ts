import type { PublicModule } from '../api/modules'

// Preview fixture: one known module plus six explicitly labelled placeholders.
// These records contain only player-public introductory information.
export const previewModules: PublicModule[] = [
  {
    id: 'darkness-beneath-the-hill',
    caseNumber: '001',
    title: '岭下暗影',
    englishTitle: 'The Darkness Beneath the Hill',
    status: 'preview',
    cover: '/images/beneath-the-hill.webp',
    introduction: [
      '1920 年代，普罗维登斯。',
      '你的熟人乔什·文斯考特，近日在自家地窖中发现了一条隧道。他邀请你前来，一同探查通道背后的秘密。',
    ],
    era: '1920 年代',
    location: '普罗维登斯',
    playStyle: '单人调查',
    originalPlayers: '2–6 人',
    contentNote: '恐怖、暴力与涉及奴隶制、种族歧视的历史背景',
  },
  ...Array.from({ length: 6 }, (_, index): PublicModule => ({
    id: `upcoming-${index + 2}`,
    caseNumber: String(index + 2).padStart(3, '0'),
    title: '待收录卷宗',
    status: 'coming-soon',
    introduction: ['这份卷宗尚未开放。新的案件与未知的故事，将在这里等待你的到来。'],
    era: '待公布',
    location: '待公布',
    playStyle: '待公布',
    originalPlayers: '待公布',
  })),
]
