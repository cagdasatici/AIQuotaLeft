import SwiftUI
import WidgetKit

struct SmallWidgetView: View {
    let entry: QuotaEntry

    var body: some View {
        if let snap = entry.snapshot {
            dataView(snap)
                .containerBackground(.fill.tertiary, for: .widget)
        } else {
            noDataView
                .containerBackground(.fill.tertiary, for: .widget)
        }
    }

    private func dataView(_ snap: UsageSnapshot) -> some View {
        let providers = entry.providers
        let iconSize: CGFloat = providers.count > 2 ? 22 : 28
        let fontSize: CGFloat = providers.count > 2 ? 18 : 24

        return HStack(spacing: 0) {
            ForEach(Array(providers.enumerated()), id: \.offset) { _, provider in
                providerGauge(snap: snap, provider: provider, iconSize: iconSize, fontSize: fontSize)
                    .frame(maxWidth: .infinity)
            }
        }
    }

    private func providerGauge(snap: UsageSnapshot, provider: AIProvider,
                               iconSize: CGFloat, fontSize: CGFloat) -> some View {
        let data = provider.displayData(from: snap)
        // No usable reading: show a dash, never "100%" left.
        let hasReading = data.isConfigured && data.error == nil
        return VStack(spacing: 6) {
            providerIcon(provider, size: iconSize)
            if hasReading {
                Text("\(data.mainRemainingPct)%")
                    .font(.system(size: fontSize, weight: .medium, design: .rounded))
                    .foregroundStyle(colorForRemaining(data.mainRemainingPct, accent: provider.color))
            } else {
                Text("\u{2014}")
                    .font(.system(size: fontSize, weight: .medium, design: .rounded))
                    .foregroundStyle(.secondary)
            }
        }
    }

    @ViewBuilder
    private func providerIcon(_ provider: AIProvider, size: CGFloat) -> some View {
        if provider.iconNeedsTemplate {
            Image(provider.iconName)
                .renderingMode(.template)
                .resizable()
                .aspectRatio(contentMode: .fit)
                .frame(width: size, height: size)
                .foregroundStyle(provider.color)
        } else {
            Image(provider.iconName)
                .resizable()
                .aspectRatio(contentMode: .fit)
                .frame(width: size, height: size)
        }
    }

    private var noDataView: some View {
        VStack(spacing: 6) {
            Image(systemName: "chart.bar")
                .font(.title2)
                .foregroundStyle(.tertiary)
            Text("No Data")
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
    }

    private func colorForRemaining(_ remaining: Int, accent: Color) -> Color {
        if remaining <= 5 { return .red }
        if remaining <= 20 { return .orange }
        return accent
    }
}
