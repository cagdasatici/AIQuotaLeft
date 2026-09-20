import WidgetKit

struct QuotaEntry: TimelineEntry {
    let date: Date
    let snapshot: UsageSnapshot?
    let isStale: Bool
    let providers: [AIProvider]

    static let placeholder = QuotaEntry(
        date: .now,
        snapshot: UsageSnapshot(
            version: 1,
            updatedAt: ISO8601DateFormatter().string(from: .now),
            claude: ClaudeUsage(
                session: LimitRow(label: "5-hour", pct: 36, resetStr: "resets Fri 00:39"),
                weeklyAll: LimitRow(label: "Weekly", pct: 83, resetStr: "resets Wed 23:00"),
                weeklySonnet: nil,
                overagesEnabled: false
            ),
            chatgpt: ChatGPTUsage(
                rows: [
                    LimitRow(label: "5-hour", pct: 12, resetStr: "resets Thu 05:38"),
                    LimitRow(label: "Weekly", pct: 41, resetStr: "resets Wed 23:00"),
                ],
                error: nil
            ),
            claudeCode: ClaudeCodeUsage(todayMessages: 42, weekMessages: 312),
            activeProviders: ["claude", "chatgpt"],
            barProviders: nil
        ),
        isStale: false,
        providers: [.claude, .chatgpt]
    )

    static let empty = QuotaEntry(
        date: .now,
        snapshot: nil,
        isStale: false,
        providers: [.claude, .chatgpt]
    )
}
