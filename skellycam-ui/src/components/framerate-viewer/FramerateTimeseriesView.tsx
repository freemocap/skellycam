// src/components/framerate-viewer/FramerateTimeseriesView.tsx
import {useCallback, useRef} from "react"
import * as d3 from "d3"
import {useTheme} from "@mui/material/styles"
import {DetailedFramerate, TimestampedSample} from "@/services/server/server-helpers/framerate-store"
import {applyAxisStyles, createTooltip} from "@/components/framerate-viewer/d3ChartUtils"
import BaseD3ChartView, {ChartScaffolding, ChartLifecycle} from "@/components/framerate-viewer/BaseD3ChartView"
import {useTranslation} from "react-i18next"

type FramerateTimeseriesProps = {
    frontendFramerate: DetailedFramerate | null
    backendFramerate: DetailedFramerate | null
    recentFrontendDurations: TimestampedSample[]
    recentBackendDurations: TimestampedSample[]
    frontendColor: string
    backendColor: string
    title?: string
}

type FpsSample = { timestamp: number; value: number }

/** How many seconds of data the rolling window shows. */
const WINDOW_SECONDS = 60

const toFps = (samples: TimestampedSample[]): FpsSample[] =>
    samples.filter((s) => s.value > 0).map((s) => ({timestamp: s.timestamp, value: 1000 / s.value}))

/**
 * Persistent mutable state shared between initChart and updateChart.
 * Stored in a ref so it survives across data updates without triggering
 * React re-renders or D3 DOM teardown.
 */
type ChartState = {
    frontendPath: d3.Selection<SVGPathElement, unknown, null, undefined>
    backendPath: d3.Selection<SVGPathElement, unknown, null, undefined>
    xScale: d3.ScaleTime<number, number>
    yScale: d3.ScaleLinear<number, number>
    tooltip: d3.Selection<HTMLDivElement, unknown, HTMLElement, any>
    // Current data snapshots for bisect-based tooltip lookup
    frontendData: FpsSample[]
    backendData: FpsSample[]
    sources: Array<{id: string; name: string; color: string}>
}

export default function FramerateTimeseriesView({
    frontendFramerate,
    backendFramerate,
    recentFrontendDurations,
    recentBackendDurations,
    frontendColor,
    backendColor,
    title = "Framerate Over Time",
}: FramerateTimeseriesProps) {
    const theme = useTheme()
    const {t} = useTranslation()
    const stateRef = useRef<ChartState | null>(null)

    // initChart — creates persistent SVG elements that live for the chart's lifetime
    const initChart = useCallback(
        ({chartArea, width, height}: ChartScaffolding): ChartLifecycle => {
            const tooltip = createTooltip(theme)

            const xScale = d3.scaleTime().range([0, width])
            const yScale = d3.scaleLinear().range([height, 0])

            // Persistent path elements — one per series, never removed
            const frontendPath = chartArea.append("path")
                .attr("fill", "none")
                .attr("stroke", frontendColor)
                .attr("stroke-width", 1.5)

            const backendPath = chartArea.append("path")
                .attr("fill", "none")
                .attr("stroke", backendColor)
                .attr("stroke-width", 1.5)

            // Persistent empty-state text (hidden by default)
            chartArea.append("text")
                .attr("class", "empty-text")
                .attr("x", width / 2)
                .attr("y", height / 2)
                .attr("text-anchor", "middle")
                .attr("dominant-baseline", "central")
                .style("font-family", "monospace")
                .style("font-size", "12px")
                .style("fill", theme.palette.text.disabled)
                .style("display", "none")

            // Invisible overlay rect for bisect-based tooltip — single event listener
            const overlay = chartArea.append("rect")
                .attr("width", width)
                .attr("height", height)
                .attr("fill", "none")
                .attr("pointer-events", "all")

            overlay.on("mousemove", (event: MouseEvent) => {
                const state = stateRef.current
                if (!state) return

                const [mx] = d3.pointer(event)
                const mouseTime = state.xScale.invert(mx).getTime()

                // Find nearest point across both series using bisect
                let bestDist = Infinity
                let bestSample: FpsSample | null = null
                let bestSource: {id: string; name: string; color: string} | null = null

                const datasets = [
                    {data: state.frontendData, source: state.sources[0]},
                    {data: state.backendData, source: state.sources[1]},
                ]

                for (const {data, source} of datasets) {
                    if (data.length === 0) continue
                    const bisect = d3.bisector<FpsSample, number>((d) => d.timestamp).center
                    const idx = bisect(data, mouseTime)
                    const sample = data[idx]
                    if (!sample) continue
                    const dist = Math.abs(sample.timestamp - mouseTime)
                    if (dist < bestDist) {
                        bestDist = dist
                        bestSample = sample
                        bestSource = source
                    }
                }

                if (bestSample && bestSource) {
                    tooltip
                        .style("opacity", 1)
                        .html(
                            `<div style="display: grid; grid-template-columns: auto auto; gap: 4px;">
                <span style="color: ${theme.palette.text.secondary};">SOURCE:</span>
                <span style="color: ${bestSource.color};">${bestSource.name}</span>
                <span style="color: ${theme.palette.text.secondary};">TIME:</span>
                <span>${new Date(bestSample.timestamp).toISOString().substr(11, 12)}</span>
                <span style="color: ${theme.palette.text.secondary};">FPS:</span>
                <span>${bestSample.value.toFixed(2)}</span>
                <span style="color: ${theme.palette.text.secondary};">DURATION:</span>
                <span>${(1000 / bestSample.value).toFixed(2)} ms</span>
              </div>`
                        )
                        .style("left", event.pageX + 10 + "px")
                        .style("top", event.pageY - 28 + "px")
                }
            })

            overlay.on("mouseleave", () => {
                tooltip.style("opacity", 0)
            })

            stateRef.current = {
                frontendPath,
                backendPath,
                xScale,
                yScale,
                tooltip,
                frontendData: [],
                backendData: [],
                sources: [
                    {id: "frontend", name: "", color: frontendColor},
                    {id: "backend", name: "", color: backendColor},
                ],
            }

            return {
                cleanup: () => {
                    tooltip.remove()
                    stateRef.current = null
                },
            }
        },
        [theme, frontendColor, backendColor]
    )

    // updateChart — only mutates existing elements, zero DOM adds/removes
    const updateChart = useCallback(
        ({svg, xAxisG, yAxisG, width, height}: ChartScaffolding) => {
            const state = stateRef.current
            if (!state) return

            const frontendFps = toFps(recentFrontendDurations)
            const backendFps = toFps(recentBackendDurations)

            // Update source names for tooltip display
            state.sources[0].name = frontendFramerate?.framerate_source || t("display")
            state.sources[1].name = backendFramerate?.framerate_source || t("server")

            const allData = [...frontendFps, ...backendFps]
            const emptyText = svg.select<SVGTextElement>(".empty-text")

            if (allData.length === 0) {
                state.frontendPath.attr("d", null)
                state.backendPath.attr("d", null)
                emptyText.style("display", null).text(t("waitingForData"))
                return
            }

            emptyText.style("display", "none")

            // Compute the rolling window
            const latestTimestamp = Math.max(...allData.map((d) => d.timestamp))
            const windowEnd = latestTimestamp
            const windowStart = windowEnd - WINDOW_SECONDS * 1000

            const windowedFrontend = frontendFps.filter((d) => d.timestamp >= windowStart)
            const windowedBackend = backendFps.filter((d) => d.timestamp >= windowStart)

            // Store windowed data for bisect tooltip lookup
            state.frontendData = windowedFrontend
            state.backendData = windowedBackend

            const visibleData = [...windowedFrontend, ...windowedBackend]
            if (visibleData.length === 0) {
                state.frontendPath.attr("d", null)
                state.backendPath.attr("d", null)
                emptyText.style("display", null).text(t("waitingForData"))
                return
            }

            // Update scale domains
            const yMax = d3.max(visibleData, (d) => d.value) as number
            const yMin = d3.min(visibleData, (d) => d.value) as number
            const yRange = yMax - yMin
            const yPadding = Math.max(1, yRange * 0.3)

            state.xScale.domain([new Date(windowStart), new Date(windowEnd)])
            state.yScale.domain([Math.max(0, yMin - yPadding), yMax + yPadding])

            // Update axes in-place
            const xAxisGen = d3
                .axisBottom(state.xScale)
                .ticks(Math.max(2, Math.min(5, Math.floor(width / 120))))
                .tickSize(-height)
                .tickFormat(d3.timeFormat("%H:%M:%S") as any)

            const yAxisGen = d3
                .axisLeft(state.yScale)
                .ticks(Math.max(2, Math.min(5, Math.floor(height / 30))))
                .tickSize(-width)

            xAxisG.call(xAxisGen)
            yAxisG.call(yAxisGen)
            applyAxisStyles(svg, theme)

            // Update path d attributes — the only DOM mutation per update
            const line = d3
                .line<FpsSample>()
                .x((d) => state.xScale(new Date(d.timestamp)))
                .y((d) => state.yScale(d.value))
                .curve(d3.curveLinear)

            state.frontendPath.attr("d", windowedFrontend.length > 0 ? line(windowedFrontend) : null)
            state.backendPath.attr("d", windowedBackend.length > 0 ? line(windowedBackend) : null)
        },
        [frontendFramerate, backendFramerate, recentFrontendDurations, recentBackendDurations, frontendColor, backendColor, theme, t]
    )

    return <BaseD3ChartView title={title} initChart={initChart} updateChart={updateChart}
                            margin={{top: 20, right: 10, bottom: 35, left: 35}}/>
}
