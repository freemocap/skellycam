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
 * Build histogram bins with a domain tight to the actual data range
 * and 1-fps-wide bins (scaling up if the range is very large).
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

    const tooltipRef = useRef<d3.Selection<HTMLDivElement, unknown, HTMLElement, any> | null>(null)

    // initChart — called once on mount/resize, creates the tooltip
    const initChart = useCallback(
        (_scaffolding: ChartScaffolding): ChartLifecycle => {
            tooltipRef.current?.remove()
            const tooltip = createTooltip(theme)
            tooltipRef.current = tooltip

            return {
                cleanup: () => {
                    tooltip.remove()
                    tooltipRef.current = null
                },
            }
        },
        [theme]
    )

    // updateChart — called on every data poll, does in-place D3 updates
    const updateChart = useCallback(
        ({svg, chartArea, xAxisG, yAxisG, width, height}: ChartScaffolding) => {
            const frontendFps = recentFrontendDurations.filter((s) => s.value > 0).map((s) => 1000 / s.value)
            const backendFps = recentBackendDurations.filter((s) => s.value > 0).map((s) => 1000 / s.value)

            const sources = [
                {
                    id: "frontend",
                    name: frontendFramerate?.framerate_source || t("display"),
                    color: frontendColor,
                    hist: buildHistogram(frontendFps),
                },
                {
                    id: "backend",
                    name: backendFramerate?.framerate_source || t("server"),
                    color: backendColor,
                    hist: buildHistogram(backendFps),
                },
            ]

            // Clear previous data elements (but NOT axes groups or clip paths)
            chartArea.selectAll("*").remove()
            svg.selectAll(".empty-text").remove()

            if (sources.every((s) => !s.hist)) {
                svg.append("text")
                    .attr("class", "empty-text")
                    .attr("x", width / 2)
                    .attr("y", height / 2)
                    .attr("text-anchor", "middle")
                    .attr("dominant-baseline", "central")
                    .style("font-family", "monospace")
                    .style("font-size", "12px")
                    .style("fill", theme.palette.text.disabled)
                    .text(t("waitingForData"))
                return
            }

            // Domain from all histogram bins
            let minX = Infinity
            let maxX = -Infinity
            let maxDensity = 0

            for (const s of sources) {
                if (!s.hist) continue
                const bins = s.hist.bins
                if (bins.length > 0) {
                    minX = Math.min(minX, bins[0].x0)
                    maxX = Math.max(maxX, bins[bins.length - 1].x1)
                }
                maxDensity = Math.max(maxDensity, s.hist.maxDensity)
            }

            if (minX === Infinity) minX = 0
            if (maxX === -Infinity) maxX = 60
            if (maxDensity === 0) maxDensity = 1

            const xPad = Math.max(1, (maxX - minX) * 0.05)

            const xScale = d3
                .scaleLinear()
                .domain([minX - xPad, maxX + xPad])
                .range([0, width])
            const yScale = d3
                .scaleLinear()
                .domain([0, maxDensity * 1.15])
                .range([height, 0])

            // Update axes in-place
            const xAxisGen = d3
                .axisBottom(xScale)
                .ticks(Math.max(2, Math.min(8, Math.floor(width / 50))))
                .tickSize(-height)
            const yAxisGen = d3
                .axisLeft(yScale)
                .ticks(Math.max(2, Math.min(5, Math.floor(height / 30))))
                .tickSize(-width)

            xAxisG.call(xAxisGen)
            yAxisG.call(yAxisGen)
            applyAxisStyles(svg, theme)

            // Draw bars
            const barInset = sources.filter((s) => s.hist).length > 1 ? 1 : 0
            const tooltip = tooltipRef.current

            sources.forEach((source, srcIdx) => {
                if (!source.hist) return

                chartArea
                    .selectAll(`.bar-${source.id}`)
                    .data(source.hist.bins)
                    .enter()
                    .append("rect")
                    .attr("class", `bar-${source.id}`)
                    .attr("x", (d) => xScale(d.x0) + srcIdx * barInset)
                    .attr("width", (d) => {
                        const w = xScale(d.x1) - xScale(d.x0) - barInset
                        return Math.max(1, w)
                    })
                    .attr("y", (d) => {
                        const y = yScale(d.density)
                        return isNaN(y) ? height : Math.min(height, Math.max(0, y))
                    })
                    .attr("height", (d) => {
                        const y = yScale(d.density)
                        if (isNaN(y)) return 0
                        return Math.max(0, height - Math.min(height, Math.max(0, y)))
                    })
                    .attr("fill", source.color)
                    .attr("stroke", theme.palette.background.paper)
                    .attr("stroke-width", 0.5)
                    .attr("opacity", 0.7)
            })

            // Attach tooltip events
            if (tooltip) {
                sources.forEach((source) => {
                    if (!source.hist) return

                    chartArea
                        .selectAll(`.bar-${source.id}`)
                        .on("mouseover", function (event, d: any) {
                            d3.select(this).attr("opacity", 1).attr("stroke-width", 1)

                            tooltip
                                .style("opacity", 1)
                                .html(
                                    `<div style="display: grid; grid-template-columns: auto auto; gap: 4px;">
                    <span style="color: ${theme.palette.text.secondary};">SOURCE:</span>
                    <span style="color: ${source.color};">${source.name}</span>
                    <span style="color: ${theme.palette.text.secondary};">RANGE:</span>
                    <span>${d.x0.toFixed(1)} – ${d.x1.toFixed(1)} fps</span>
                    <span style="color: ${theme.palette.text.secondary};">COUNT:</span>
                    <span>${d.count} samples</span>
                    <span style="color: ${theme.palette.text.secondary};">PERCENTAGE:</span>
                    <span>${(d.density * 100).toFixed(1)}%</span>
                  </div>`
                                )
                                .style("left", event.pageX + 10 + "px")
                                .style("top", event.pageY - 28 + "px")
                        })
                        .on("mouseout", function () {
                            d3.select(this).attr("opacity", 0.7).attr("stroke-width", 0.5)
                            tooltip.style("opacity", 0)
                        })
                })
            }
        },
        [frontendFramerate, backendFramerate, recentFrontendDurations, recentBackendDurations, frontendColor, backendColor, theme, t]
    )

    return <BaseD3ChartView title={title} initChart={initChart} updateChart={updateChart}
                            margin={{top: 20, right: 10, bottom: 35, left: 35}} />
}
