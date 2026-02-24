// src/components/framerate-viewer/FramerateHistogramView.tsx
import {useCallback} from "react"
import * as d3 from "d3"
import {useTheme} from "@mui/material/styles"
import {applyAxisStyles, createTooltip, renderEmptyChart} from "./d3ChartUtils"
import {DetailedFramerate, TimestampedSample} from "@/services/server/server-helpers/framerate-store"
import BaseD3ChartView from "@/components/framerate-viewer/BaseD3ChartView"
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

    const renderChart = useCallback(
        ({
            svg,
            chartArea,
            width,
            height,
        }: {
            svg: d3.Selection<SVGGElement, unknown, null, undefined>
            chartArea: d3.Selection<SVGGElement, unknown, null, undefined>
            width: number
            height: number
            margin: {top: number; right: number; bottom: number; left: number}
        }) => {
            // Extract fps values from timestamped duration samples
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

            if (sources.every((s) => !s.hist)) {
                renderEmptyChart(svg, width, height, theme, t("waitingForData"))
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

            // Axes (initial, no zoom)
            const xAxisG = svg
                .append("g")
                .attr("class", "x-axis")
                .attr("transform", `translate(0,${height})`)
            const yAxisG = svg.append("g").attr("class", "y-axis")

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

            // Tooltip
            const tooltip = createTooltip(theme)

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

            // Zoom handler: updates axes + bar positions via D3 without React re-render
            const onZoom = (transform: d3.ZoomTransform): void => {
                const xz = transform.rescaleX(xScale)
                const yz = transform.rescaleY(yScale)

                xAxisG.call(xAxisGen.scale(xz))
                yAxisG.call(yAxisGen.scale(yz))
                applyAxisStyles(svg, theme)

                sources.forEach((source, srcIdx) => {
                    if (!source.hist) return
                    chartArea
                        .selectAll<SVGRectElement, HistogramBin>(`.bar-${source.id}`)
                        .attr("x", (d) => xz(d.x0) + srcIdx * barInset)
                        .attr("width", (d) => Math.max(1, xz(d.x1) - xz(d.x0) - barInset))
                        .attr("y", (d) => {
                            const y = yz(d.density)
                            return isNaN(y) ? height : Math.min(height, Math.max(0, y))
                        })
                        .attr("height", (d) => {
                            const y = yz(d.density)
                            if (isNaN(y)) return 0
                            return Math.max(0, height - Math.min(height, Math.max(0, y)))
                        })
                })
            }

            return {
                onZoom,
                cleanup: () => tooltip.remove(),
            }
        },
        [frontendFramerate, backendFramerate, recentFrontendDurations, recentBackendDurations, frontendColor, backendColor, theme]
    )

    return <BaseD3ChartView title={title} renderChart={renderChart} margin={{top: 20, right: 10, bottom: 35, left: 35}} />
}
