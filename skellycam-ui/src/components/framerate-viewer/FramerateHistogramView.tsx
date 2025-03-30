// src/components/framerate-viewer/FramerateHistogramView.tsx
import {useEffect, useRef, useState} from "react"
import * as d3 from "d3"
import {Box, Fade, IconButton, Tooltip, Typography} from "@mui/material"
import {useTheme} from "@mui/material/styles"
import {RestartAlt, ZoomIn, ZoomOut} from "@mui/icons-material"
import { CurrentFramerate } from "../../store/slices/framerateTrackerSlice"

type FramerateHistogramProps = {
  frontendFramerate: CurrentFramerate | null
  backendFramerate: CurrentFramerate | null
  recentFrontendFrameDurations: number[]
  recentBackendFrameDurations: number[]
  title?: string
}

export default function FramerateHistogramView({
  frontendFramerate,
  backendFramerate,
  recentFrontendFrameDurations,
  recentBackendFrameDurations,
  title = "Frame Duration Distribution",
}: FramerateHistogramProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  const theme = useTheme()
  const [transform, setTransform] = useState<d3.ZoomTransform>(d3.zoomIdentity)
  const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null)
  const [showControls, setShowControls] = useState(false)

  useEffect(() => {
    if (!svgRef.current) return

    // Clear previous chart
    d3.select(svgRef.current).selectAll("*").remove()

    // Create local histogram data based on recent frame durations
    // This is a good place to create a histogram now that we don't get it directly from the backend
    const generateHistogram = (data: number[], binCount = 20) => {
      if (data.length === 0) return null;

      // Calculate bins using d3's histogram generator
      const histGenerator = d3.histogram()
        .domain([0, d3.max(data) as number * 1.1]) // Add 10% padding to max
        .thresholds(binCount);

      const bins = histGenerator(data);

      // Calculate densities (normalized counts)
      const totalCount = data.length;
      const binCounts = bins.map(bin => bin.length);
      const binDensities = binCounts.map(count => count / totalCount);

      return {
        bin_edges: bins.map(bin => bin.x0 as number),
        bin_counts: binCounts,
        bin_densities: binDensities
      };
    };

    // Prepare the sources with histogram data
    const sources = [
      {
        id: 'frontend',
        name: frontendFramerate?.framerate_source || 'Frontend',
        color: theme.palette.primary.main,
        histogram: generateHistogram(recentFrontendFrameDurations),
        totalSamples: recentFrontendFrameDurations.length
      },
      {
        id: 'backend',
        name: backendFramerate?.framerate_source || 'Backend',
        color: theme.palette.secondary.main,
        histogram: generateHistogram(recentBackendFrameDurations),
        totalSamples: recentBackendFrameDurations.length
      }
    ];

    // Check if we have valid histogram data
    if (sources.every(s => !s.histogram)) {
      // Draw empty chart with axes
      const margin = { top: 20, right: 30, bottom: 30, left: 60 }
      const width = svgRef.current.clientWidth - margin.left - margin.right
      const height = svgRef.current.clientHeight - margin.top - margin.bottom

      const svg = d3.select(svgRef.current).append("g").attr("transform", `translate(${margin.left},${margin.top})`)

      // Create empty scales
      const xScale = d3.scaleLinear().domain([0, 100]).range([0, width])
      const yScale = d3.scaleLinear().domain([0, 10]).range([height, 0])

      // Create axes
      const xAxis = d3.axisBottom(xScale).ticks(10).tickSize(-height)
      const yAxis = d3.axisLeft(yScale).ticks(5).tickSize(-width)

      // Add X axis
      svg
        .append("g")
        .attr("class", "x-axis")
        .style("font-family", "monospace")
        .style("font-size", "10px")
        .style("color", theme.palette.text.secondary)
        .attr("transform", `translate(0,${height})`)
        .call(xAxis)

      // Add Y axis
      svg
        .append("g")
        .attr("class", "y-axis")
        .style("font-family", "monospace")
        .style("font-size", "10px")
        .style("color", theme.palette.text.secondary)
        .call(yAxis)

      // Style grid lines
      svg.selectAll(".tick line").attr("stroke", theme.palette.divider).attr("stroke-dasharray", "2,2")

      // Add "No data" message
      svg
        .append("text")
        .attr("x", width / 2)
        .attr("y", height / 2)
        .attr("text-anchor", "middle")
        .style("font-family", "monospace")
        .style("font-size", "14px")
        .style("fill", theme.palette.text.disabled)
        .text("No histogram data available")

      return
    }

    // Set up dimensions
    const margin = { top: 20, right: 100, bottom: 30, left: 60 }
    const width = svgRef.current.clientWidth - margin.left - margin.right
    const height = svgRef.current.clientHeight - margin.top - margin.bottom

    // Create SVG with a clip path for zooming
    const svg = d3.select(svgRef.current).append("g").attr("transform", `translate(${margin.left},${margin.top})`)

    // Add clip path to prevent drawing outside the chart area
    svg
      .append("defs")
      .append("clipPath")
      .attr("id", "clip-histogram")
      .append("rect")
      .attr("width", width)
      .attr("height", height)

    // Create a group for the chart content that will be clipped
    const chartArea = svg.append("g").attr("clip-path", "url(#clip-histogram)")

    // Find domain bounds from all histograms
    let minX = Infinity
    let maxX = -Infinity
    let maxDensity = 0

    sources.forEach(source => {
      if (source.histogram) {
        const edges = source.histogram.bin_edges
        const densities = source.histogram.bin_densities

        if (edges.length > 0) {
          minX = Math.min(minX, edges[0])
          maxX = Math.max(maxX, edges[edges.length - 1])
        }

        if (densities.length > 0) {
          maxDensity = Math.max(maxDensity, Math.max(...densities))
        }
      }
    })

    // If we couldn't determine bounds, use defaults
    if (minX === Infinity) minX = 0
    if (maxX === -Infinity) maxX = 100
    if (maxDensity === 0) maxDensity = 1

    // Add padding to domain
    const xPadding = (maxX - minX) * 0.1
    const xDomain = [Math.max(0, minX - xPadding), maxX + xPadding]

    // Set up scales
    const xScale = d3.scaleLinear().domain(xDomain).range([0, width])
    const yScale = d3.scaleLinear().domain([0, maxDensity * 1.1]).range([height, 0])

    // Apply the current zoom transform
    const xScaleZoomed = transform.rescaleX(xScale)
    const yScaleZoomed = transform.rescaleY(yScale)

    // Create axes
    const xAxis = d3.axisBottom(xScaleZoomed).ticks(10).tickSize(-height)
    const yAxis = d3.axisLeft(yScaleZoomed).ticks(5).tickSize(-width)

    // Add X axis with label
    const xAxisGroup = svg
      .append("g")
      .attr("class", "x-axis")
      .style("font-family", "monospace")
      .style("font-size", "10px")
      .style("color", theme.palette.text.secondary)
      .attr("transform", `translate(0,${height})`)
      .call(xAxis)

    svg
      .append("text")
      .attr("transform", `translate(${width / 2}, ${height + margin.bottom - 5})`)
      .style("text-anchor", "middle")
      .style("font-family", "monospace")
      .style("font-size", "10px")
      .style("fill", theme.palette.text.secondary)
      .text("Frame Duration (ms)")

    // Add Y axis with label
    const yAxisGroup = svg
      .append("g")
      .attr("class", "y-axis")
      .style("font-family", "monospace")
      .style("font-size", "10px")
      .style("color", theme.palette.text.secondary)
      .call(yAxis)

    svg
      .append("text")
      .attr("transform", "rotate(-90)")
      .attr("y", 0 - margin.left)
      .attr("x", 0 - height / 2)
      .attr("dy", "1em")
      .style("text-anchor", "middle")
      .style("font-family", "monospace")
      .style("font-size", "10px")
      .style("fill", theme.palette.text.secondary)
      .text("Density")

    // Style grid lines
    svg.selectAll(".tick line").attr("stroke", theme.palette.divider).attr("stroke-dasharray", "2,2")

    // Add threshold lines (e.g., 16.67ms for 60fps, 33.33ms for 30fps)
    const thresholds = [
      { value: 16.67, label: "60 FPS", color: theme.palette.success.main },
      { value: 33.33, label: "30 FPS", color: theme.palette.warning.main },
    ]

    thresholds.forEach((threshold) => {
      if (threshold.value <= maxX + xPadding) {
        // Add threshold line
        chartArea
            .append("line")
            .attr("x1", xScaleZoomed(threshold.value))
            .attr("y1", 0)
            .attr("x2", xScaleZoomed(threshold.value))
            .attr("y2", height)
            .attr("stroke", threshold.color)
            .attr("stroke-width", 1.5)
            .attr("stroke-dasharray", "4,4")

        // Add threshold label
        chartArea
            .append("text")
            .attr("x", xScaleZoomed(threshold.value))
            .attr("y", 15)
            .attr("text-anchor", "middle")
            .style("font-family", "monospace")
            .style("font-size", "10px")
            .style("fill", threshold.color)
            .text(threshold.label)
      }
    })

    // Draw histograms using our calculated values
    sources.forEach(source => {
      if (!source.histogram || source.histogram.bin_edges.length === 0) return

      const bins = source.histogram.bin_edges.map((edge, i) => ({
        x0: edge,
        x1: i < source.histogram!.bin_edges.length - 1 ? source.histogram!.bin_edges[i + 1] : edge + 0.1,
        density: i < source.histogram!.bin_densities.length ? source.histogram!.bin_densities[i] : 0,
        count: i < source.histogram!.bin_counts.length ? source.histogram!.bin_counts[i] : 0
      }))

      // Add histogram bars
      chartArea
          .selectAll(`.bar-${source.id}`)
          .data(bins)
          .enter()
          .append("rect")
          .attr("class", `bar-${source.id}`)
          .attr("x", d => xScaleZoomed(d.x0))
          .attr("y", d => yScaleZoomed(d.density))
          .attr("width", d => Math.max(0, xScaleZoomed(d.x1) - xScaleZoomed(d.x0) - 1))
          .attr("height", d => height - yScaleZoomed(d.density))
          .attr("fill", source.color)
          .attr("stroke", theme.palette.background.paper)
          .attr("stroke-width", 0.5)
          .attr("opacity", 0.7)
    })

    // Add legend
    const legend = svg
        .append("g")
        .attr("transform", `translate(${width + 10}, 0)`)
        .attr("font-family", "monospace")
        .attr("font-size", "10px")

    sources.forEach((source, i) => {
      if (!source.histogram) return

      const legendItem = legend.append("g").attr("transform", `translate(0, ${i * 20})`)
      legendItem.append("rect").attr("width", 12).attr("height", 12).attr("fill", source.color)
      legendItem.append("text")
          .attr("x", 20)
          .attr("y", 10)
          .style("fill", theme.palette.text.primary)
          .text(`${source.name} (${source.totalSamples})`)
    })

    // Add tooltip functionality
    const tooltip = d3
        .select("body")
        .append("div")
        .style("position", "absolute")
        .style("background-color", theme.palette.mode === "dark" ? "rgba(0, 0, 0, 0.85)" : "rgba(255, 255, 255, 0.9)")
        .style("border", `1px solid ${theme.palette.divider}`)
        .style("border-radius", "4px")
        .style("padding", "8px")
        .style("font-family", "monospace")
        .style("font-size", "12px")
        .style("pointer-events", "none")
        .style("opacity", 0)
        .style("z-index", 1000)
        .style("color", theme.palette.text.primary)

    // Add tooltip for histogram bars
    sources.forEach(source => {
      if (!source.histogram) return

      chartArea
          .selectAll(`.bar-${source.id}`)
          .on("mouseover", function (event, d: any) {
            d3.select(this).attr("opacity", 1).attr("stroke-width", 1)

            tooltip
                .style("opacity", 1)
                .html(`
              <div style="display: grid; grid-template-columns: auto auto; gap: 4px;">
                <span style="color: ${theme.palette.text.secondary};">SOURCE:</span>
                <span style="color: ${source.color};">${source.name}</span>
                <span style="color: ${theme.palette.text.secondary};">RANGE:</span>
                <span>${d.x0.toFixed(2)} - ${d.x1.toFixed(2)} ms</span>
                <span style="color: ${theme.palette.text.secondary};">COUNT:</span>
                <span>${d.count} samples</span>
                <span style="color: ${theme.palette.text.secondary};">PERCENTAGE:</span>
                <span>${(d.density * 100).toFixed(1)}%</span>
                <span style="color: ${theme.palette.text.secondary};">FPS RANGE:</span>
                <span>${(1000 / d.x1).toFixed(1)} - ${(1000 / d.x0).toFixed(1)} fps</span>
              </div>
            `)
                .style("left", event.pageX + 10 + "px")
                .style("top", event.pageY - 28 + "px")
          })
          .on("mouseout", function () {
            d3.select(this).attr("opacity", 0.7).attr("stroke-width", 0.5)
            tooltip.style("opacity", 0)
          })
    })

    // Define zoom behavior
    const zoom = d3
        .zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.5, 20])
        .extent([
          [0, 0],
          [width, height],
        ])
        .on("zoom", (event) => {
          // Update the transform state
          setTransform(event.transform)

          // Update axes with the new scales
          xAxisGroup.call(xAxis.scale(event.transform.rescaleX(xScale)))
          yAxisGroup.call(yAxis.scale(event.transform.rescaleY(yScale)))

          // Update histogram bars
          sources.forEach(source => {
            if (!source.histogram) return

            chartArea
                .selectAll(`.bar-${source.id}`)
                .attr("x", (d: any) => event.transform.applyX(xScale(d.x0)))
                .attr("y", (d: any) => event.transform.applyY(yScale(d.density)))
                .attr("width", (d: any) => Math.max(0, event.transform.k * (xScale(d.x1) - xScale(d.x0)) - 1))
                .attr("height", (d: any) => height - event.transform.applyY(yScale(d.density)))
          })

          // Update threshold lines
          thresholds.forEach((threshold) => {
            if (threshold.value <= maxX + xPadding) {
              chartArea
                  .selectAll("line")
                  .filter(function () {
                    return d3.select(this).attr("x1") === xScale(threshold.value).toString()
                  })
                  .attr("x1", event.transform.applyX(xScale(threshold.value)))
                  .attr("x2", event.transform.applyX(xScale(threshold.value)))

              chartArea
                  .selectAll("text")
                  .filter(function () {
                    return d3.select(this).text() === threshold.label
                  })
                  .attr("x", event.transform.applyX(xScale(threshold.value)))
            }
          })
        })

    // Store zoom reference for external controls
    zoomRef.current = zoom

    // Apply zoom to the SVG
    d3.select(svgRef.current).call(zoom)

    // Clean up tooltip on unmount
    return () => {
      tooltip.remove()
    }
  }, [frontendFramerate, backendFramerate, recentFrontendFrameDurations, recentBackendFrameDurations, theme, transform])

  // Zoom control handlers
  const handleZoomIn = () => {
    if (svgRef.current && zoomRef.current) {
      d3.select(svgRef.current).transition().duration(300).call(zoomRef.current.scaleBy, 1.5)
    }
  }

  const handleZoomOut = () => {
    if (svgRef.current && zoomRef.current) {
      d3.select(svgRef.current).transition().duration(300).call(zoomRef.current.scaleBy, 0.75)
    }
  }

  const handleResetZoom = () => {
    if (svgRef.current && zoomRef.current) {
      d3.select(svgRef.current).transition().duration(300).call(zoomRef.current.transform, d3.zoomIdentity)
    }
  }

  return (
      <Box
          sx={{
            width: "100%",
            height: "100%",
            position: "relative",
            overflow: "hidden" // Prevent overflow
          }}
          onMouseEnter={() => setShowControls(true)}
          onMouseLeave={() => setShowControls(false)}
      >
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
            <Tooltip title="Zoom In" placement="right">
              <IconButton size="small" onClick={handleZoomIn} sx={{ p: 0.5 }}>
                <ZoomIn fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title="Zoom Out" placement="right">
              <IconButton size="small" onClick={handleZoomOut} sx={{ p: 0.5 }}>
                <ZoomOut fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title="Reset Zoom" placement="right">
              <IconButton size="small" onClick={handleResetZoom} sx={{ p: 0.5 }}>
                <RestartAlt fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
        </Fade>

        <svg
            ref={svgRef}
            width="100%"
            height="100%"
            style={{
              display: 'block', // Important for proper sizing
              overflow: "visible"
            }}
        />
      </Box>
  )
}
