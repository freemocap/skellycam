// src/components/framerate-viewer/BaseD3ChartView.tsx
import {useEffect, useRef, useState, useCallback} from "react"
import * as d3 from "d3"
import {Box, Fade, IconButton, Tooltip, Typography} from "@mui/material"
import {RestartAlt, ZoomIn, ZoomOut} from "@mui/icons-material"
import { useTranslation } from "react-i18next";

export type ChartMargins = {
    top: number
    right: number
    bottom: number
    left: number
}

export type ZoomableElement = {
    selector: string;
    updateFn: (selection: d3.Selection<any, any, any, any>, transform: d3.ZoomTransform) => void;
}

type BaseChartViewProps = {
    title?: string
    renderChart: (params: {
        svg: d3.Selection<SVGGElement, unknown, null, undefined>
        chartArea: d3.Selection<SVGGElement, unknown, null, undefined>
        width: number
        height: number
        margin: ChartMargins
        transform: d3.ZoomTransform
    }) => void
    margin?: ChartMargins
}

export default function BaseD3ChartView({
                                            title,
                                            renderChart,
                                            margin = {top: 20, right: 20, bottom: 30, left: 50}
                                        }: BaseChartViewProps) {
    const { t } = useTranslation();
    const svgRef = useRef<SVGSVGElement>(null)
    const containerRef = useRef<HTMLDivElement>(null)
    const chartRef = useRef<{
        cleanup?: () => void
    }>({})
    const [transform, setTransform] = useState<d3.ZoomTransform>(d3.zoomIdentity)
    const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null)
    const [showControls, setShowControls] = useState(false)
    const [containerSize, setContainerSize] = useState<{width: number, height: number}>({width: 0, height: 0})

    // Track container size with ResizeObserver
    useEffect(() => {
        const container = containerRef.current
        if (!container) return

        const observer = new ResizeObserver((entries) => {
            for (const entry of entries) {
                const {width, height} = entry.contentRect
                setContainerSize(prev => {
                    if (prev.width === Math.round(width) && prev.height === Math.round(height)) return prev
                    return {width: Math.round(width), height: Math.round(height)}
                })
            }
        })
        observer.observe(container)
        return () => observer.disconnect()
    }, [])

    useEffect(() => {
        if (!svgRef.current || containerSize.width === 0 || containerSize.height === 0) return

        // Clear previous chart
        d3.select(svgRef.current).selectAll("*").remove()

        // Cleanup previous tooltips
        if (chartRef.current.cleanup) {
            chartRef.current.cleanup()
            chartRef.current.cleanup = undefined
        }

        // Set up dimensions from observed container size
        const width = Math.max(0, containerSize.width - margin.left - margin.right)
        const height = Math.max(0, containerSize.height - margin.top - margin.bottom)

        if (width <= 0 || height <= 0) return

        // Create SVG group with margin offset
        const svg = d3.select(svgRef.current)
            .append("g")
            .attr("transform", `translate(${margin.left},${margin.top})`)

        // Add clip path to prevent drawing outside the chart area
        svg
            .append("defs")
            .append("clipPath")
            .attr("id", "clip-chart")
            .append("rect")
            .attr("width", width)
            .attr("height", height)

        // Create a group for the chart content that will be clipped
        const chartArea = svg.append("g").attr("clip-path", "url(#clip-chart)")

        // Call the render function provided by the child component
        const cleanup = renderChart({svg, chartArea, width, height, margin, transform})

        if (typeof cleanup === 'function') {
            chartRef.current.cleanup = cleanup
        }

        // Define zoom behavior
        const zoom = d3
            .zoom<SVGSVGElement, unknown>()
            .scaleExtent([0.5, 20])
            .extent([
                [0, 0],
                [width, height],
            ])
            .on("zoom", (event) => {
                setTransform(event.transform)
            })

        zoomRef.current = zoom
        d3.select(svgRef.current).call(zoom)

        return () => {
            if (chartRef.current.cleanup) {
                chartRef.current.cleanup()
                chartRef.current.cleanup = undefined
            }
        }
    }, [renderChart, margin, transform, containerSize])

    const handleZoomIn = useCallback(() => {
        if (svgRef.current && zoomRef.current) {
            d3.select(svgRef.current).transition().duration(300).call(zoomRef.current.scaleBy, 1.5)
        }
    }, [])

    const handleZoomOut = useCallback(() => {
        if (svgRef.current && zoomRef.current) {
            d3.select(svgRef.current).transition().duration(300).call(zoomRef.current.scaleBy, 0.75)
        }
    }, [])

    const handleResetZoom = useCallback(() => {
        if (svgRef.current && zoomRef.current) {
            d3.select(svgRef.current).transition().duration(300).call(zoomRef.current.transform, d3.zoomIdentity)
        }
    }, [])

    return (
        <Box
            ref={containerRef}
            sx={{
                width: "100%",
                height: "100%",
                position: "relative",
                overflow: "hidden"
            }}
            onMouseEnter={() => setShowControls(true)}
            onMouseLeave={() => setShowControls(false)}
        >
            {title && (
                <Typography
                    variant="caption"
                    sx={{
                        position: "absolute",
                        top: 5,
                        left: 10,
                        fontSize: '0.7rem',
                        opacity: 0.8
                    }}
                >
                    {title}
                </Typography>
            )}

            {/* Zoom controls that fade in/out on hover */}
            <Fade in={showControls}>
                <Box
                    sx={{
                        position: "absolute",
                        top: "50%",
                        right: 5,
                        transform: "translateY(-50%)",
                        zIndex: 10,
                        bgcolor: "background.paper",
                        borderRadius: 1,
                        boxShadow: 1,
                        display: "flex",
                        flexDirection: "column",
                    }}
                >
                    <Tooltip title={t("zoomIn")} placement="right">
                        <IconButton size="small" onClick={handleZoomIn} sx={{p: 0.5}}>
                            <ZoomIn fontSize="small"/>
                        </IconButton>
                    </Tooltip>
                    <Tooltip title={t("zoomOut")} placement="right">
                        <IconButton size="small" onClick={handleZoomOut} sx={{p: 0.5}}>
                            <ZoomOut fontSize="small"/>
                        </IconButton>
                    </Tooltip>
                    <Tooltip title={t("resetZoom")} placement="right">
                        <IconButton size="small" onClick={handleResetZoom} sx={{p: 0.5}}>
                            <RestartAlt fontSize="small"/>
                        </IconButton>
                    </Tooltip>
                </Box>
            </Fade>

            <svg
                ref={svgRef}
                width={containerSize.width}
                height={containerSize.height}
                style={{
                    display: 'block',
                    overflow: "hidden"
                }}
            />
        </Box>
    )
}
