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

    // Mutable ref holding the tooltip so it survives across data updates
    const tooltipRef = useRef<d3.Selection<HTMLDivElement, unknown, HTMLElement, any> | null>(null)

    // initChart — called once on mount/resize, creates the tooltip
    const initChart = useCallback(
        (_scaffolding: ChartScaffolding): ChartLifecycle => {
            // Clean up any previous tooltip (shouldn't happen, but safety)
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
        // theme is stable within a session (only changes on light/dark toggle)
        [theme]
    )

    // updateChart — called on every data poll, does in-place D3 updates
    const updateChart = useCallback(
        ({svg, chartArea, xAxisG, yAxisG, width, height}: ChartScaffolding) => {
            const sources = [
                {
                    id: "frontend",
                    name: frontendFramerate?.framerate_source || t("display"),
                    color: frontendColor,
                    data: toFps(recentFrontendDurations),
                },
                {
                    id: "backend",
                    name: backendFramerate?.framerate_source || t("server"),
                    color: backendColor,
                    data: toFps(recentBackendDurations),
                },
            ]

            // Clear previous data elements (but NOT axes groups or clip paths)
            chartArea.selectAll("*").remove()
            // Clear any previous empty-chart text on the svg group
            svg.selectAll(".empty-text").remove()

            if (sources.every((s) => s.data.length === 0)) {
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

            // Determine the window from the actual data timestamps
            const allTimestamps = sources.flatMap((s) => s.data.map((d) => d.timestamp))
            const latestTimestamp = Math.max(...allTimestamps)
            const windowEnd = latestTimestamp
            const windowStart = windowEnd - WINDOW_SECONDS * 1000

            const windowedSources = sources.map((s) => ({
                ...s,
                data: s.data.filter((d) => d.timestamp >= windowStart),
            }))

            const visibleData = windowedSources.flatMap((s) => s.data)
            if (visibleData.length === 0) {
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

            // Y domain from visible data
            const yMax = d3.max(visibleData, (d) => d.value) as number
            const yMin = d3.min(visibleData, (d) => d.value) as number
            const yRange = yMax - yMin
            const yPadding = Math.max(1, yRange * 0.3)

            const xScale = d3
                .scaleTime()
                .domain([new Date(windowStart), new Date(windowEnd)])
                .range([0, width])

            const yScale = d3
                .scaleLinear()
                .domain([Math.max(0, yMin - yPadding), yMax + yPadding])
                .range([height, 0])

            // Update axes in-place (reusing the persistent axis groups)
            const xAxisGen = d3
                .axisBottom(xScale)
                .ticks(Math.max(2, Math.min(5, Math.floor(width / 120))))
                .tickSize(-height)
                .tickFormat(d3.timeFormat("%H:%M:%S") as any)

            const yAxisGen = d3
                .axisLeft(yScale)
                .ticks(Math.max(2, Math.min(5, Math.floor(height / 30))))
                .tickSize(-width)

            xAxisG.call(xAxisGen)
            yAxisG.call(yAxisGen)
            applyAxisStyles(svg, theme)

            // Line generator
            const line = d3
                .line<FpsSample>()
                .x((d) => xScale(new Date(d.timestamp)))
                .y((d) => yScale(d.value))
                .curve(d3.curveLinear)

            // Draw lines and dots into the persistent chartArea
            const tooltip = tooltipRef.current

            windowedSources.forEach((source) => {
                if (source.data.length === 0) return

                chartArea
                    .append("path")
                    .datum(source.data)
                    .attr("class", `line-${source.id}`)
                    .attr("fill", "none")
                    .attr("stroke", source.color)
                    .attr("stroke-width", 1.5)
                    .attr("d", line)

                chartArea
                    .selectAll(`.dot-${source.id}`)
                    .data(source.data)
                    .enter()
                    .append("circle")
                    .attr("class", `dot-${source.id}`)
                    .attr("cx", (d) => xScale(new Date(d.timestamp)))
                    .attr("cy", (d) => yScale(d.value))
                    .attr("r", 2)
                    .attr("fill", source.color)
                    .attr("opacity", 0.8)
            })

            // Attach tooltip events
            if (tooltip) {
                windowedSources.forEach((source) => {
                    if (source.data.length === 0) return

                    chartArea.selectAll(`.dot-${source.id}`)
                        .on("mouseover", function (event: MouseEvent, d: any) {
                            const element = this as unknown as SVGCircleElement
                            d3.select(element)
                                .attr("r", 5)
                                .attr("fill", d3.color(source.color)!.brighter(0.5).toString())

                            tooltip
                                .style("opacity", 1)
                                .html(
                                    `<div style="display: grid; grid-template-columns: auto auto; gap: 4px;">
                    <span style="color: ${theme.palette.text.secondary};">SOURCE:</span>
                    <span style="color: ${source.color};">${source.name}</span>
                    <span style="color: ${theme.palette.text.secondary};">TIME:</span>
                    <span>${new Date(d.timestamp).toISOString().substr(11, 12)}</span>
                    <span style="color: ${theme.palette.text.secondary};">FPS:</span>
                    <span>${d.value.toFixed(2)}</span>
                    <span style="color: ${theme.palette.text.secondary};">DURATION:</span>
                    <span>${(1000 / d.value).toFixed(2)} ms</span>
                  </div>`
                                )
                                .style("left", event.pageX + 10 + "px")
                                .style("top", event.pageY - 28 + "px")
                        })
                        .on("mouseout", function () {
                            d3.select(this).attr("r", 2).attr("fill", source.color)
                            tooltip.style("opacity", 0)
                        })
                })
            }
        },
        [frontendFramerate, backendFramerate, recentFrontendDurations, recentBackendDurations, frontendColor, backendColor, theme, t]
    )

    return <BaseD3ChartView title={title} initChart={initChart} updateChart={updateChart}
                            margin={{top: 20, right: 10, bottom: 35, left: 35}}/>
}
