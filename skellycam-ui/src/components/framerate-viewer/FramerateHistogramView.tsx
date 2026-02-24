// src/components/framerate-viewer/FramerateHistogramView.tsx
import {useCallback, useRef} from "react"
import * as d3 from "d3"
import {useTheme} from "@mui/material/styles"
import {applyAxisStyles, createTooltip} from "./d3ChartUtils"
import {DetailedFramerate, TimestampedSample} from "@/services/server/server-helpers/framerate-store"
import BaseD3ChartView, {ChartScaffolding, ChartLifecycle} from "@/components/framerate-viewer/BaseD3ChartView"
import {useTranslation} from "react-i18next"

type FramerateHistogramProps = {
    frontendFramerate: DetailedFramerate | null
    backendFramerate: DetailedFramerate | null
    recentFrontendDurations: TimestampedSample[]
    recentBackendDurations: TimestampedSample[]
    frontendColor: string
    backendColor: string
    title?: string
}

type HistogramBin = {x0: number; x1: number; count: number; density: number}

/**
 * Build histogram bins with a domain tight to the actual data range.
 */
function buildHistogram(fpsValues: number[]): {
    bins: HistogramBin[]
    maxDensity: number
} | null {
    if (fpsValues.length === 0) return null

    const min = Math.floor(d3.min(fpsValues)!)
    const max = Math.ceil(d3.max(fpsValues)!)

    const range = max - min
    const binWidth = range > 40 ? Math.ceil(range / 30) : 1
    const thresholds: number[] = []
    for (let v = min; v <= max; v += binWidth) {
        thresholds.push(v)
    }

    const generator = d3
        .bin<number, number>()
        .domain([min, max + binWidth])
        .thresholds(thresholds)

    const rawBins = generator(fpsValues)
    const total = fpsValues.length
    let maxDensity = 0

    const bins = rawBins.map((b) => {
        const density = b.length / total
        if (density > maxDensity) maxDensity = density
        return {
            x0: b.x0 as number,
            x1: b.x1 as number,
            count: b.length,
            density,
        }
    })

    return {bins, maxDensity}
}

/**
 * Persistent mutable state shared between initChart and updateChart.
 */
type ChartState = {
    frontendBarGroup: d3.Selection<SVGGElement, unknown, null, undefined>
    backendBarGroup: d3.Selection<SVGGElement, unknown, null, undefined>
    xScale: d3.ScaleLinear<number, number>
    yScale: d3.ScaleLinear<number, number>
    tooltip: d3.Selection<HTMLDivElement, unknown, HTMLElement, any>
    sources: Array<{id: string; name: string; color: string; bins: HistogramBin[]}>
    height: number
}

export default function FramerateHistogramView({
    frontendFramerate,
    backendFramerate,
    recentFrontendDurations,
    recentBackendDurations,
    frontendColor,
    backendColor,
    title = "Framerate Distribution",
}: FramerateHistogramProps) {
    const theme = useTheme()
    const {t} = useTranslation()
    const stateRef = useRef<ChartState | null>(null)

    // initChart — creates persistent groups and a single hover overlay
    const initChart = useCallback(
        ({chartArea, width, height}: ChartScaffolding): ChartLifecycle => {
            const tooltip = createTooltip(theme)

            const xScale = d3.scaleLinear().range([0, width])
            const yScale = d3.scaleLinear().range([height, 0])

            // Persistent bar groups — one per series, never removed
            const frontendBarGroup = chartArea.append("g").attr("class", "bars-frontend")
            const backendBarGroup = chartArea.append("g").attr("class", "bars-backend")

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

            // Invisible overlay for tooltip — single event listener
            const overlay = chartArea.append("rect")
                .attr("width", width)
                .attr("height", height)
                .attr("fill", "none")
                .attr("pointer-events", "all")

            overlay.on("mousemove", (event: MouseEvent) => {
                const state = stateRef.current
                if (!state) return

                const [mx] = d3.pointer(event)
                const mouseX = state.xScale.invert(mx)

                // Find which bin the mouse is over, across both series
                let bestBin: HistogramBin | null = null
                let bestSource: {name: string; color: string} | null = null

                for (const source of state.sources) {
                    for (const bin of source.bins) {
                        if (mouseX >= bin.x0 && mouseX < bin.x1) {
                            // Prefer the bin with higher density if overlapping
                            if (!bestBin || bin.density > bestBin.density) {
                                bestBin = bin
                                bestSource = source
                            }
                        }
                    }
                }

                if (bestBin && bestSource) {
                    tooltip
                        .style("opacity", 1)
                        .html(
                            `<div style="display: grid; grid-template-columns: auto auto; gap: 4px;">
                <span style="color: ${theme.palette.text.secondary};">SOURCE:</span>
                <span style="color: ${bestSource.color};">${bestSource.name}</span>
                <span style="color: ${theme.palette.text.secondary};">RANGE:</span>
                <span>${bestBin.x0.toFixed(1)} – ${bestBin.x1.toFixed(1)} fps</span>
                <span style="color: ${theme.palette.text.secondary};">COUNT:</span>
                <span>${bestBin.count} samples</span>
                <span style="color: ${theme.palette.text.secondary};">PERCENTAGE:</span>
                <span>${(bestBin.density * 100).toFixed(1)}%</span>
              </div>`
                        )
                        .style("left", event.pageX + 10 + "px")
                        .style("top", event.pageY - 28 + "px")
                } else {
                    tooltip.style("opacity", 0)
                }
            })

            overlay.on("mouseleave", () => {
                tooltip.style("opacity", 0)
            })

            stateRef.current = {
                frontendBarGroup,
                backendBarGroup,
                xScale,
                yScale,
                tooltip,
                sources: [
                    {id: "frontend", name: "", color: frontendColor, bins: []},
                    {id: "backend", name: "", color: backendColor, bins: []},
                ],
                height,
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

    // updateChart — uses D3 data join for minimal DOM mutations
    const updateChart = useCallback(
        ({svg, chartArea, xAxisG, yAxisG, width, height}: ChartScaffolding) => {
            const state = stateRef.current
            if (!state) return

            const frontendFps = recentFrontendDurations.filter((s) => s.value > 0).map((s) => 1000 / s.value)
            const backendFps = recentBackendDurations.filter((s) => s.value > 0).map((s) => 1000 / s.value)

            const frontendHist = buildHistogram(frontendFps)
            const backendHist = buildHistogram(backendFps)

            // Update source metadata for tooltip
            state.sources[0].name = frontendFramerate?.framerate_source || t("display")
            state.sources[1].name = backendFramerate?.framerate_source || t("server")
            state.sources[0].bins = frontendHist?.bins ?? []
            state.sources[1].bins = backendHist?.bins ?? []
            state.height = height

            const emptyText = chartArea.select<SVGTextElement>(".empty-text")

            if (!frontendHist && !backendHist) {
                // Clear all bars
                state.frontendBarGroup.selectAll("rect").remove()
                state.backendBarGroup.selectAll("rect").remove()
                emptyText.style("display", null).text(t("waitingForData"))
                return
            }

            emptyText.style("display", "none")

            // Compute domain from all bins
            let minX = Infinity
            let maxX = -Infinity
            let maxDensity = 0

            for (const hist of [frontendHist, backendHist]) {
                if (!hist) continue
                const bins = hist.bins
                if (bins.length > 0) {
                    minX = Math.min(minX, bins[0].x0)
                    maxX = Math.max(maxX, bins[bins.length - 1].x1)
                }
                maxDensity = Math.max(maxDensity, hist.maxDensity)
            }

            if (minX === Infinity) minX = 0
            if (maxX === -Infinity) maxX = 60
            if (maxDensity === 0) maxDensity = 1

            const xPad = Math.max(1, (maxX - minX) * 0.05)

            state.xScale.domain([minX - xPad, maxX + xPad])
            state.yScale.domain([0, maxDensity * 1.15])

            // Update axes in-place
            const xAxisGen = d3
                .axisBottom(state.xScale)
                .ticks(Math.max(2, Math.min(8, Math.floor(width / 50))))
                .tickSize(-height)
            const yAxisGen = d3
                .axisLeft(state.yScale)
                .ticks(Math.max(2, Math.min(5, Math.floor(height / 30))))
                .tickSize(-width)

            xAxisG.call(xAxisGen)
            yAxisG.call(yAxisGen)
            applyAxisStyles(svg, theme)

            // D3 data join for bars — enter/update/exit pattern
            const numSources = [frontendHist, backendHist].filter(Boolean).length
            const barInset = numSources > 1 ? 1 : 0

            const updateBars = (
                group: d3.Selection<SVGGElement, unknown, null, undefined>,
                bins: HistogramBin[],
                color: string,
                srcIdx: number,
            ) => {
                const bars = group.selectAll<SVGRectElement, HistogramBin>("rect")
                    .data(bins, (d) => `${d.x0}-${d.x1}`)

                // EXIT: remove bars for bins that no longer exist
                bars.exit().remove()

                // ENTER: create new bars
                const entered = bars.enter()
                    .append("rect")
                    .attr("fill", color)
                    .attr("stroke", theme.palette.background.paper)
                    .attr("stroke-width", 0.5)
                    .attr("opacity", 0.7)

                // UPDATE + ENTER: update positions and sizes for all bars
                entered.merge(bars)
                    .attr("x", (d) => state.xScale(d.x0) + srcIdx * barInset)
                    .attr("width", (d) => {
                        const w = state.xScale(d.x1) - state.xScale(d.x0) - barInset
                        return Math.max(1, w)
                    })
                    .attr("y", (d) => {
                        const y = state.yScale(d.density)
                        return isNaN(y) ? height : Math.min(height, Math.max(0, y))
                    })
                    .attr("height", (d) => {
                        const y = state.yScale(d.density)
                        if (isNaN(y)) return 0
                        return Math.max(0, height - Math.min(height, Math.max(0, y)))
                    })
            }

            updateBars(state.frontendBarGroup, frontendHist?.bins ?? [], frontendColor, 0)
            updateBars(state.backendBarGroup, backendHist?.bins ?? [], backendColor, numSources > 1 ? 1 : 0)
        },
        [frontendFramerate, backendFramerate, recentFrontendDurations, recentBackendDurations, frontendColor, backendColor, theme, t]
    )

    return <BaseD3ChartView title={title} initChart={initChart} updateChart={updateChart}
                            margin={{top: 20, right: 10, bottom: 35, left: 35}} />
}
